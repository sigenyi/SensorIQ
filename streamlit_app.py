import streamlit as st
import pandas as pd
import anthropic
import os
from streamlit_gsheets import GSheetsConnection

# --- 1. SETUP ---
# Sonnet 4.6 handles baseline synthesis (strong reasoning + adaptive thinking, cost-efficient).
# Opus 4.7 handles refinement — when the tech is stuck mid-session and needs the deepest
# reasoning to escape a loop or diagnose an unusual combination, this is where it matters most.
BASELINE_MODEL = "claude-sonnet-4-6"
REFINEMENT_MODEL = "claude-opus-4-7"

# Behavioral rules shared by BOTH models so guidance and tone stay consistent.
SHARED_RULES = """
CHANGE SIZING: Match the size of each change to how far the image is from acceptable. Use small ~5-10% steps to fine-tune a nearly-correct image, but make ONE decisive, correctly-sized move when the image is clearly off — do not under-correct out of caution. Boundary values are LEGITIMATE and often correct: HP=100, LP=0, Gamma=0.35 or 0.85, CLAHE Regions 2x2 or 8x8, Sharpen Weight 2.00. Do NOT shy from extremes when the diagnosis calls for them. The only hard limit is safety: never make a jump that risks clipping highlights/shadows or pushing the sensor toward saturation.

ANTI-LOOP / NON-REGRESSION: In a refinement turn, inspect every prior attempt in this session BEFORE recommending changes. If a setting was already adjusted in an earlier round, do NOT revert it without strong cause — that creates oscillation loops where the tech ends up back where they started. After two rounds in the same direction without resolution, STOP repeating the same parameters. Step back, re-diagnose the root cause, and propose a fundamentally different approach — a different escalation tier, a hardware re-check, or a re-analysis of which symptom is actually the underlying problem. Acknowledge the loop in your CAUSE line if you are breaking out of one.

ADAPTIVE NORMALIZATION PERCENTILES — CORRECT MECHANIC: HP and LP are CUTOFF POINTS, not "amounts to remove."
- HP=N preserves brightness data up to the Nth percentile; the top (100-N)% is clipped. HP=100 keeps ALL bright detail (brightest image, full highlight gradation). HP=99 trims top 1%. HP=95 trims top 5% (noticeably darker, significant bright detail lost).
- LP=N preserves dark data above the Nth percentile; the bottom N% is clipped. LP=0 keeps ALL dark detail. LP=1 trims darkest 1%. LP=5 trims darkest 5% (cleaner shadows, lost dark gradation).
- For a TOO-DARK image, the first AN move is usually RAISE HP toward 100. For genuinely over-exposed / blown-out highlights, LOWER HP toward 95-97 to clip the bad data.

HARDWARE & BINNING DISCIPLINE: This is a post-capture SOFTWARE tool. Do NOT default to changing exposure time or enabling 2x2 Binning when stuck. Recommend an exposure-time change ONLY for genuine under/over-exposure or saturation (verified against quick_guide ranges); recommend 2x2 Binning ONLY for a weak X-ray source or diagnosed sensor fatigue. Otherwise work the software ladder first: AN -> CLAHE -> Gamma -> Sharpening -> Contrast/Brightness.

CONTRAST & BRIGHTNESS: Lower priority than the data-preserving software ladder, and you should prefer AN / CLAHE / Gamma / Sharpening first because Contrast and Brightness modify linear display values rather than the underlying pixel data. HOWEVER, they are LEGITIMATE TOOLS — NOT banned. Use them when the ladder has been worked and further adjustment would help, particularly Contrast, which can produce real perceived-detail improvement even on already-optimized data. Recommend them when they would meaningfully improve diagnostic perception. Do not treat them as untouchable.

CLAHE: Whenever you adjust CLAHE, you MUST specify BOTH Clip Limit AND Num Regions X/Y (range 2-8, i.e. 2x2 to 8x8). Use finer grids (7x7-8x8) for trabecular/PDL/perio detail; coarser grids (2x2-4x4) for broad, smooth contrast. Never omit Num Regions.

EXPOSURE UNITS: Exposure may be given in seconds, milliseconds, a fraction (1/n s), or pulses (1 pulse = 1/60 s = 0.0167 s). If you recommend an exposure change, express it in the SAME unit the technician is using (e.g. "+1 pulse -> 7 pulses = ~0.117 s", "shorten to 1/10 s"). Convert the second-based quick_guide ranges into that unit first.

GAMMA: Lower Gamma = brighter mid-tones; higher Gamma = darker mid-tones. Range 0.35-0.85 (capped at 0.85).
"""

try:
    client = anthropic.Anthropic(api_key=st.secrets["CLAUDE_KEY"])
except Exception:
    st.error("Missing CLAUDE_KEY in Streamlit Secrets!")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)

# --- 2. HELPERS ---
def load_technical_manuals():
    paths = [
        "knowledge/quick_guide.txt",
        "knowledge/settings_guide.txt",
        "knowledge/radiography_guide.txt",
        "knowledge/sensor_model.txt",
        "knowledge/differential_diagnosis.txt",
        "knowledge/success_criteria.txt",
    ]
    combined = ""
    for path in paths:
        if os.path.exists(path):
            with open(path, "r") as f:
                combined += f"\n--- {path.upper()} ---\n{f.read()}\n"
    return combined if combined else "Technical manuals not found."

def check_saturation_risk(kvp, ma, exposure, machine):
    warnings = []
    mas = round(ma * exposure, 3)
    if machine == "Wall-mounted":
        if kvp >= 80:
            warnings.append(f"kVp={kvp} is high (>=80). Over-penetration risk — image may appear flat/gray regardless of software settings.")
        if mas > 1.0:
            warnings.append(f"mAs={mas} is elevated. Sensor saturation risk — software cannot recover clipped data.")
    elif machine == "Hand-held":
        if kvp >= 75:
            warnings.append(f"kVp={kvp} is high for a hand-held unit. Over-penetration risk.")
        if mas > 3.0:
            warnings.append(f"mAs={mas} is elevated for a hand-held unit. Saturation risk.")
    return warnings

def get_ai_baseline(software, machine, hardware_specs, diagnostic_goal, df, knowledge):
    history = df[(df['software'] == software) & (df['machine'] == machine)]
    past_logs = history.tail(10).to_string(index=False) if not history.empty else "No history found."

    prompt = f"""
You are a Senior Dental Imaging Specialist. Synthesize a recommended baseline for:
Software: {software} | Machine: {machine}
Hardware: {hardware_specs}
Diagnostic Goal: {diagnostic_goal}

KNOWLEDGE BASE:
{knowledge}

PAST CALIBRATION LOGS FOR THIS SETUP:
{past_logs}

RULES:
- Check sensor saturation risk from sensor_model.txt first.
- Pull proven settings from past logs if available.
- Match the diagnostic goal to the correct recipe from quick_guide.txt.
- Verify parameter combinations against the interaction matrix in sensor_model.txt.
- Radiopaque (bone/enamel) = White. Radiolucent (air/decay) = Black.
- Contrast/Brightness are lower priority than AN/CLAHE/Gamma/Sharpening but are LEGITIMATE — recommend them when they would meaningfully improve diagnostic perception (especially Contrast), not as untouchable last resorts.
{SHARED_RULES}

OUTPUT — return EXACTLY this structure, nothing else:
HARDWARE: [Safe — or flag the specific risk in one short line]
SETTINGS:
- [SettingName]: [value]
- [SettingName]: [value]
- CLAHE Regions: [XxY]   (include this line whenever CLAHE is part of the baseline)
NOTES: [Goal optimized for, plus any one-line caution. Keep it brief.]
"""
    try:
        response = client.messages.create(
            model=BASELINE_MODEL,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        return f"Baseline unavailable — {str(e)}"

def get_ai_refinement(software, machine, hardware_specs, diagnostic_goal,
                      current_baseline, refinement_history, new_feedback, knowledge):
    # Build prior-attempt context so the AI cannot ignore what has already been tried.
    # This block is given visual prominence and is positioned at the TOP of the prompt
    # because oscillation loops are the failure mode it must prevent.
    attempt_num = len(refinement_history) + 1
    history_block = ""
    if refinement_history:
        history_block = (
            "═══ PREVIOUS ATTEMPTS IN THIS SESSION — READ CAREFULLY BEFORE RECOMMENDING ═══\n"
            f"This is attempt #{attempt_num}. The prior attempts below already changed settings. "
            "Before recommending anything new, identify which settings have already been touched. "
            "Do NOT revert them without strong cause, and do NOT re-suggest parameters that have "
            "already been tried — that produces oscillation loops.\n"
        )
        for i, entry in enumerate(refinement_history, 1):
            history_block += (
                f"\n--- Attempt {i} ---\n"
                f"Issue raised: {entry['feedback']}\n"
                f"Advice given:\n{entry['response']}\n"
            )
        if attempt_num >= 3:
            history_block += (
                "\n⚠ THIS IS ATTEMPT #" + str(attempt_num) + ". Two or more rounds have already failed to resolve the issue. "
                "Do NOT propose the same parameters again. Step back, re-diagnose the root cause, "
                "and recommend a fundamentally different approach (different tier, hardware re-check, "
                "or re-analysis of which symptom is actually the problem). Acknowledge in your CAUSE "
                "line that you are breaking out of the prior pattern.\n"
            )
        history_block += "\n═══ END OF PRIOR ATTEMPTS ═══\n"

    prompt = f"""
You are a Senior Dental Imaging Specialist. The technician is mid-session with a client; your job is to actually reason through the problem and produce a fix that works, not just satisfy the output format. Give a short, direct answer — cause and changes only.

{history_block}

Setup: {software} | {machine}
Hardware: {hardware_specs}
Diagnostic Goal: {diagnostic_goal}
Current Baseline: {current_baseline}

NEW ISSUE: {new_feedback}

KNOWLEDGE BASE:
{knowledge}

REASONING (do this silently — do NOT write out the steps in your answer):
- Check sensor saturation from sensor_model.txt.
- Map symptom to differential_diagnosis.txt categories A-G. Find the actual root cause, not just the surface symptom.
- Follow escalation order: hardware first only if truly warranted, then AN, CLAHE, Gamma, Sharpening, then Contrast/Brightness (lower priority but not forbidden).
- Check parameter interaction matrix in sensor_model.txt Section 5.
- Cross-check prior attempts above. If you are about to recommend a change that was already tried (or that would revert a previous change), STOP and choose a different approach.
{SHARED_RULES}

OUTPUT — return EXACTLY this structure, nothing more, nothing less:
CAUSE: [One sentence maximum. If breaking out of a prior loop, acknowledge it here.]
SETTINGS:
- [Setting]: [old value] → [new value]
- [Setting]: [old value] → [new value]
- CLAHE Regions: [oldXxY] → [newXxY]   (include this line whenever you change CLAHE)
NOTES: [One-line risk warning, or "None".]
---LOGDATA---
LOG_ISSUE:[concise_snake_case_tag]
LOG_SETTINGS:[SettingName: Value, SettingName: Value, SettingName: Value]
---ENDLOG---
"""
    try:
        response = client.messages.create(
            model=REFINEMENT_MODEL,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        return f"Analysis error — {str(e)}"

def parse_refinement_response(full_text):
    """Split on delimiters so display text and log data never bleed into each other."""
    log_issue = "general"
    log_settings = "none"
    display_text = full_text  # safe fallback

    if "---LOGDATA---" in full_text and "---ENDLOG---" in full_text:
        parts = full_text.split("---LOGDATA---")
        display_text = parts[0].strip()
        log_block = parts[1].split("---ENDLOG---")[0].strip()
        for line in log_block.splitlines():
            line = line.strip()
            if line.startswith("LOG_ISSUE:"):
                log_issue = line[len("LOG_ISSUE:"):].strip()
            elif line.startswith("LOG_SETTINGS:"):
                log_settings = line[len("LOG_SETTINGS:"):].strip()

    return display_text, log_issue, log_settings

def log_to_google_sheets(software, machine, issue, settings, notes):
    try:
        existing_data = conn.read()
        new_entry = pd.DataFrame([{
            "machine": machine,
            "software": software,
            "issue": issue,
            "settings": settings,
            "notes": notes.strip() if notes.strip() else "none",
        }])
        updated_df = pd.concat([existing_data, new_entry], ignore_index=True)
        conn.update(data=updated_df)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Database error: {e}")
        return False

def full_reset():
    for k in ['baseline_generated', 'current_baseline', 'last_setup',
              'refinement_history', 'last_issue', 'last_settings']:
        if k in st.session_state:
            del st.session_state[k]
    st.toast("Reset complete.")

# --- 3. LOAD DATA ---
knowledge_context = load_technical_manuals()
try:
    df_history = conn.read()
except Exception:
    df_history = pd.DataFrame(columns=['machine', 'software', 'issue', 'settings', 'notes'])

# --- 4. UI CONFIG ---
st.set_page_config(page_title="Jazz AI Image Quality", page_icon="🦷")
st.markdown("""
<style>
div[data-testid="stTextArea"] textarea {
    background-color: #f0f2f6 !important;
    border: 1px solid #d1d5db !important;
}
.sat-box {
    background-color: #f8d7da;
    border-left: 5px solid #dc3545;
    padding: 10px 12px;
    border-radius: 4px;
    margin: 6px 0;
    font-size: 0.88em;
}
</style>
""", unsafe_allow_html=True)

st.title("🦷 Jazz AI Image Quality Assistant")

# --- 5. SIDEBAR ---
st.sidebar.header("Initial Setup")
machine = st.sidebar.selectbox("X-ray Source", ["Select...", "Wall-mounted", "Hand-held"], index=0)
software_options = ["Select..."] + sorted([
    "CDR DICOM", "Carestream", "Dentrix Ascend", "DEXIS", "Eaglesoft", "Sidexis", "Vixwin",
    "XDR", "Edge Cloud", "Curve Hero", "Planmeca Romexis", "Oryx", "Tigerview", "Tracker",
    "iDental", "Clio", "DTX Studio", "SOTA", "EzDent-i", "Open Dental", "Tab32", "SOPRO",
    "Mipacs", "Denticon XV Capture", "Denticon XV Web", "CliniView", "Dentiray Capture",
    "Imaging XL", "Prof. Suni", "Xray Vision", "SIGMA", "PatientGallery", "Xelis Dental",
    "Overjet", "Aeka", "CLASSIC", "Archy", "Mogo", "Acteon", "VisionX", "OneView", "Umbie DentalCare",
    "Harmony", "CareStack", "OTHER"
])
software = st.sidebar.selectbox("Imaging Software", software_options, index=0)

st.sidebar.divider()
st.sidebar.header("⚙️ Hardware Settings")
kvp = st.sidebar.number_input("kVp", min_value=50, max_value=90, value=70)
ma = st.sidebar.number_input("mA", min_value=1.0, max_value=10.0, value=7.0, step=0.1)

# Exposure can be entered in whatever unit the machine uses; everything below
# is normalized to SECONDS so the mAs / saturation math is unit-agnostic.
exp_unit = st.sidebar.selectbox(
    "Exposure Unit",
    ["Seconds", "Milliseconds", "Fraction (1/n s)", "Pulses"],
    index=0
)
if exp_unit == "Seconds":
    exp_val = st.sidebar.number_input("Exposure (s)", min_value=0.01, max_value=2.00, value=0.10, step=0.01)
    exposure = exp_val
    exposure_native = f"{exp_val:.3f} s"
elif exp_unit == "Milliseconds":
    exp_val = st.sidebar.number_input("Exposure (ms)", min_value=1, max_value=2000, value=100, step=1)
    exposure = exp_val / 1000.0
    exposure_native = f"{exp_val} ms"
elif exp_unit == "Fraction (1/n s)":
    n = st.sidebar.number_input("Exposure = 1/n second — enter n", min_value=1, max_value=600, value=10, step=1)
    exposure = 1.0 / n
    exposure_native = f"1/{n} s"
else:  # Pulses
    pulses = st.sidebar.number_input("Pulses (1 pulse = 1/60 s ≈ 0.0167 s)", min_value=1, max_value=60, value=6, step=1)
    exposure = pulses * (1.0 / 60.0)
    exposure_native = f"{pulses} pulse(s)"

exposure = round(exposure, 4)
st.sidebar.caption(f"= {exposure:.3f} s  |  mAs: {round(ma * exposure, 3)}")
hardware_context = f"kVp: {kvp}, mA: {ma}, Exposure: {exposure_native} (= {exposure:.3f} s), mAs: {round(ma * exposure, 3)}"

sat_warnings = check_saturation_risk(kvp, ma, exposure, machine if machine != "Select..." else "Wall-mounted")
if sat_warnings:
    st.sidebar.divider()
    st.sidebar.markdown("**🔴 Hardware Risk**")
    for w in sat_warnings:
        st.sidebar.markdown(f'<div class="sat-box">{w}</div>', unsafe_allow_html=True)

st.sidebar.divider()
st.sidebar.header("🎯 Diagnostic Goal")
diagnostic_goal = st.sidebar.selectbox(
    "Image purpose:",
    ["General / Unknown", "Caries Detection", "Periodontal Bone Levels",
     "Endodontics (Root Canal)", "Fracture Detection", "Post-op / Healing Check"]
)

st.sidebar.markdown("---")
st.sidebar.caption("v2.1.0 | Jazz AI Support")

# --- 6. MAIN ---
if software == "Select..." or machine == "Select...":
    st.markdown("""
    <div style="text-align:center; margin-top:100px;">
        <h1 style="font-size:3.5em; margin-bottom:0;">👈 Start Here</h1>
        <p style="font-size:1.5em; color:#666;">Select the setup on the left sidebar to begin.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ── STEP 1: BASELINE ──────────────────────────────────────────────────────────
st.markdown("### 📍 Step 1: Recommended Baseline")
current_setup_id = f"{software}-{machine}-{hardware_context}-{diagnostic_goal}"

if not st.session_state.get('baseline_generated'):
    # Baseline only generates on explicit button press
    st.info("Confirm your sidebar settings, then click **Generate Baseline**.")
    if st.button("⚡ Generate Baseline", use_container_width=True):
        with st.spinner("Synthesizing baseline..."):
            st.session_state['current_baseline'] = get_ai_baseline(
                software, machine, hardware_context, diagnostic_goal,
                df_history, knowledge_context
            )
            st.session_state['last_setup'] = current_setup_id
            st.session_state['baseline_generated'] = True
            st.session_state['refinement_history'] = []
        st.rerun()
else:
    # Warn if sidebar changed after generation
    if st.session_state.get('last_setup') != current_setup_id:
        st.warning("⚠️ Setup has changed since the baseline was generated. Regenerate to match.")
        if st.button("⚡ Regenerate Baseline", use_container_width=True):
            with st.spinner("Regenerating..."):
                st.session_state['current_baseline'] = get_ai_baseline(
                    software, machine, hardware_context, diagnostic_goal,
                    df_history, knowledge_context
                )
                st.session_state['last_setup'] = current_setup_id
                st.session_state['refinement_history'] = []
            st.rerun()

    if 'current_baseline' in st.session_state:
        st.markdown(f"""
        <div style="background-color:#d4edda; padding:15px; border-radius:10px; border-left:5px solid #28a745;">
            <p style="color:#888; font-size:0.82em; margin:0 0 6px 0;">Goal: {diagnostic_goal}</p>
            <pre style="color:#155724; font-size:1.0em; white-space:pre-wrap; margin:0; font-family:inherit;">{st.session_state['current_baseline']}</pre>
        </div>
        """, unsafe_allow_html=True)

# ── STEP 2: REFINEMENT ────────────────────────────────────────────────────────
if st.session_state.get('baseline_generated') and 'current_baseline' in st.session_state:
    st.markdown("---")
    st.markdown("### 🛠️ Step 2: Refine Image Quality")

    refinement_history = st.session_state.get('refinement_history', [])

    # Show collapsed history of what's been tried
    if refinement_history:
        for i, entry in enumerate(refinement_history, 1):
            label = f"Attempt {i}: {entry['feedback'][:55]}{'…' if len(entry['feedback']) > 55 else ''}"
            with st.expander(label, expanded=(i == len(refinement_history))):
                st.markdown(entry['response'])

    # Input — label changes after first attempt to signal continuation
    label_text = "What still needs fixing?" if refinement_history else "Describe the issue after applying the baseline:"
    user_feedback = st.text_area(
        label_text,
        height=110,
        placeholder="e.g., 'Image is still too flat' or 'Bone structure not visible'..."
    )

    if st.button("🔍 Analyze Issue", use_container_width=True):
        if user_feedback.strip():
            with st.spinner("Analyzing..."):
                raw = get_ai_refinement(
                    software, machine, hardware_context, diagnostic_goal,
                    st.session_state['current_baseline'],
                    refinement_history,
                    user_feedback.strip(),
                    knowledge_context
                )
                display_text, log_issue, log_settings = parse_refinement_response(raw)
                # Append to chain, never replace
                st.session_state['refinement_history'].append({
                    "feedback": user_feedback.strip(),
                    "response": display_text,
                })
                st.session_state['last_issue'] = log_issue
                st.session_state['last_settings'] = log_settings
            st.rerun()
        else:
            st.warning("Please describe the issue before analyzing.")

    # ── Logging & navigation (only after at least one refinement) ──
    if refinement_history:
        st.markdown("---")
        st.markdown("### 📝 Log Successful Calibration")
        tech_notes = st.text_input("Tech notes (e.g., 'Client happy'):")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Log & Finish", use_container_width=True):
                with st.spinner("Logging..."):
                    ok = log_to_google_sheets(
                        software, machine,
                        st.session_state.get('last_issue', 'general'),
                        st.session_state.get('last_settings', 'none'),
                        tech_notes
                    )
                if ok:
                    st.toast("✅ Logged successfully!")
                    full_reset()
                    st.rerun()
        with col2:
            if st.button("🔄 Start Over", use_container_width=True):
                full_reset()
                st.rerun()

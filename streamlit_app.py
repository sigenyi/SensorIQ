import streamlit as st
import pandas as pd
import anthropic
import os
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- 1. SETUP MODELS & CLIENT ---
SONNET_MODEL = "claude-sonnet-4-20250514"
HAIKU_MODEL = "claude-haiku-4-5-20251001"

try:
    client = anthropic.Anthropic(api_key=st.secrets["CLAUDE_KEY"])
except Exception:
    st.error("Missing CLAUDE_KEY in Streamlit Secrets!")
    st.stop()

# --- 2. DATA CONNECTIONS & HELPER FUNCTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_technical_manuals():
    """Reads ALL TXT files from the /knowledge directory."""
    paths = [
        "knowledge/quick_guide.txt",
        "knowledge/settings_guide.txt",
        "knowledge/radiography_guide.txt",
        "knowledge/sensor_model.txt",           # sensor physics + param interactions
        "knowledge/differential_diagnosis.txt", # inverse reasoning tree
        "knowledge/success_criteria.txt",       # quantitative image quality standards
    ]
    combined_knowledge = ""
    for path in paths:
        if os.path.exists(path):
            with open(path, "r") as f:
                combined_knowledge += f"\n--- {path.upper()} ---\n{f.read()}\n"
    return combined_knowledge if combined_knowledge else "Technical manuals not found."


def clear_and_reset():
    """Clears session data for a fresh analysis."""
    keys_to_delete = [
        'current_ai_response', 'standardized_issue', 'formatted_settings',
        'current_baseline', 'last_setup', 'saturation_warning', 'diagnostic_goal'
    ]
    for key in keys_to_delete:
        if key in st.session_state:
            del st.session_state[key]
    st.toast("System Reset")


def log_to_google_sheets(software, machine, issue, settings, notes):
    """Appends successful calibration data to Google Sheets."""
    try:
        existing_data = conn.read()
        new_entry = pd.DataFrame([{
            "machine": machine,
            "software": software,
            "issue": issue,
            "settings": settings,
            "notes": notes if notes.strip() != "" else "none",
        }])
        updated_df = pd.concat([existing_data, new_entry], ignore_index=True)
        conn.update(data=updated_df)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"DATABASE ERROR: {e}")
        return False


# Detection of hardware-level problems before any AI work
def check_saturation_risk(kvp, ma, exposure, machine):
    """
    Detects conditions where sensor saturation is likely. 
    If saturated, software corrections are futile — hardware must be adjusted first.
    Based on sensor_model.txt: CMOS saturates at ~88% dynamic range.
    """
    warnings = []
    # Wall-mounted overexposure thresholds (mAs = mA * exposure)
    mas = ma * exposure
    if machine == "Wall-mounted":
        if kvp >= 80:
            warnings.append(f"⚠️ kVp={kvp} is high (≥80). Risk of over-penetration: image may appear flat/gray regardless of software settings.")
        if mas > 1.0:  # mA*s product — approximate threshold for wall-mount
            warnings.append(f"⚠️ mAs={mas:.2f} is elevated. Risk of sensor saturation. Software CANNOT recover clipped pixel data.")
    elif machine == "Hand-held":
        if kvp >= 75:
            warnings.append(f"⚠️ kVp={kvp} is high for a hand-held unit. Risk of over-penetration.")
        if mas > 3.0:
            warnings.append(f"⚠️ mAs={mas:.2f} is elevated for a hand-held unit.")
    return warnings


def get_ai_baseline(software, machine, hardware_specs, df, knowledge):
    """
    Uses SONNET to synthesize a baseline. 
    Prompt instructs the model to use the differential diagnosis 
    protocol and sensor model, not just past history and recipes.
    Baseline now references diagnostic goal context.
    """
    history = df[(df['software'] == software) & (df['machine'] == machine)]
    past_logs = history.tail(10).to_string(index=False) if not history.empty else "No history found."

    baseline_prompt = f"""
    You are a Senior Dental Imaging Specialist with deep knowledge of CMOS sensor physics.

    Synthesize a "Gold Standard" baseline for: {software} | {machine}.
    HARDWARE CONTEXT: {hardware_specs}

    KNOWLEDGE BASE (read all sections before responding):
    {knowledge}

    REASONING PROTOCOL — Follow this order:
    1. SENSOR CHECK FIRST: Based on hardware_specs, consult sensor_model.txt.
       Are the hardware settings within the safe linear range of the CMOS sensor (below ~88% saturation)?
       If kVp >= 80 or mAs is high, flag this in your baseline note.
    2. CONSULT HISTORY: Use past_logs below to identify proven settings.
    3. CONSULT RECIPES: Match quick_guide.txt diagnostic recipes to the context.
    4. APPLY INTERACTION MATRIX: From sensor_model.txt Section 5, verify that the 
       recommended combination of parameters does not create an unsafe interaction.
    5. REFERENCE SUCCESS CRITERIA: From success_criteria.txt, state which diagnostic 
       structures the baseline is optimized to reveal.

    PAST CALIBRATION LOGS FOR THIS SETUP:
    {past_logs}

    RADIOGRAPHY PHYSICS RULES:
    1. Radiopaque (dense/enamel/metal) = White. Radiolucent (air/decay/pulp) = Black.
    2. AVOID Contrast/Brightness unless Tiers 1-5 of the escalation ladder have failed.
    3. Sensor linear range is valid up to ~88% of 16,384 gray levels. Above this: hardware fix needed.

    FORMAT — Return ONLY:
    Line 1: Hardware note (confirm kVp/mAs are in safe range, or flag risk)
    Lines 2+: Concise settings list
    Last line: "Optimized for: [structure list from success_criteria.txt]"
    """
    try:
        response = client.messages.create(
            model=SONNET_MODEL,
            max_tokens=800,
            messages=[{"role": "user", "content": baseline_prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        return f"Baseline Synthesis Unavailable (Error: {str(e)})"


# --- 3. LOAD DATA ---
knowledge_context = load_technical_manuals()
try:
    df_history = conn.read()
except Exception:
    df_history = pd.DataFrame(columns=[
        'machine', 'software', 'issue', 'settings', 'notes'
    ])

# --- 4. UI CONFIGURATION ---
st.set_page_config(page_title="Jazz AI Image Quality", page_icon="🦷")

st.markdown(
    """
    <style>
    div[data-testid="stTextArea"] textarea { background-color: #f0f2f6 !important; border: 1px solid #d1d5db !important; }
    blockquote { border-left: 5px solid #28a745 !important; background-color: #f9fafb !important; padding: 10px !important; }
    .warning-box { background-color: #fff3cd; border-left: 5px solid #ffc107; padding: 12px; border-radius: 5px; margin: 8px 0; }
    .saturation-box { background-color: #f8d7da; border-left: 5px solid #dc3545; padding: 12px; border-radius: 5px; margin: 8px 0; }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🦷 Jazz AI Image Quality Assistant")

# --- 5. SIDEBAR: SETUP ---
st.sidebar.header("Initial Setup")
machine = st.sidebar.selectbox("X-ray Source", ["Select...", "Wall-mounted", "Hand-held"], index=0)

software_options = ["Select..."] + sorted([
    "CDR DICOM", "Carestream", "Dentrix Ascend", "DEXIS", "Eaglesoft", "Sidexis", "Vixwin",
    "XDR", "Edge Cloud", "Curve Hero", "Planmeca Romexis", "Oryx", "Tigerview", "Tracker",
    "iDental", "Clio", "DTX Studio", "SOTA", "EzDent-i", "Open Dental", "Tab32", "SOPRO",
    "Mipacs", "Denticon XV Capture", "Denticon XV Web", "CliniView", "Dentiray Capture",
    "Imaging XL", "Prof. Suni", "Xray Vision", "SIGMA", "PatientGallery", "Xelis Dental",
    "Overjet", "Aeka", "CLASSIC", "Archy", "OTHER", "Harmony"
])
software = st.sidebar.selectbox("Imaging Software", software_options, index=0)

st.sidebar.divider()
st.sidebar.header("⚙️ Hardware Settings")
kvp = st.sidebar.number_input("kVp (Contrast Power)", min_value=50, max_value=90, value=70)
ma = st.sidebar.number_input("mA (Photon Quantity)", min_value=1.0, max_value=10.0, value=7.0, step=0.1)
exposure = st.sidebar.number_input("Exposure (Seconds)", min_value=0.01, max_value=1.00, value=0.10, step=0.01)

hardware_context = f"kVp: {kvp}, mA: {ma}, Exposure: {exposure}s, mAs: {round(ma * exposure, 3)}"

# Show saturation warnings in the sidebar, before AI work begins
saturation_warnings = check_saturation_risk(kvp, ma, exposure, machine if machine != "Select..." else "Wall-mounted")
if saturation_warnings:
    st.sidebar.divider()
    st.sidebar.header("🔴 Hardware Risk Flags")
    for w in saturation_warnings:
        st.sidebar.markdown(f'<div class="saturation-box">{w}</div>', unsafe_allow_html=True)

# Diagnostic goal selector — shapes the AI's success criteria reference
st.sidebar.divider()
st.sidebar.header("🎯 Diagnostic Goal")
diagnostic_goal = st.sidebar.selectbox(
    "What is this image for?",
    ["General / Unknown", "Caries Detection", "Periodontal Bone Levels",
     "Endodontics (Root Canal)", "Fracture Detection", "Post-op / Healing Check"]
)

st.sidebar.markdown("---")
st.sidebar.caption("v2.0.0 | Jazz AI Support — Mechanistic Edition")


# --- 6. MAIN LOGIC ---
if software == "Select..." or machine == "Select...":
    st.markdown("""
        <div style="text-align: center; margin-top: 100px;">
            <h1 style="font-size: 3.5em; margin-bottom: 0;">👈 Start Here</h1>
            <p style="font-size: 1.5em; color: #666;">Select the setup on the left sidebar to begin.</p>
        </div>
    """, unsafe_allow_html=True)
else:
    # --- STEP 1: SMART BASELINE ---
    current_setup_id = f"{software}-{machine}-{hardware_context}-{diagnostic_goal}"
    if 'current_baseline' not in st.session_state or st.session_state.get('last_setup') != current_setup_id:
        with st.spinner("AI is synthesizing a smart baseline from sensor physics + success history..."):
            st.session_state['current_baseline'] = get_ai_baseline(
                software, machine, hardware_context, df_history, knowledge_context
            )
            st.session_state['last_setup'] = current_setup_id

    st.markdown(f"""
        <div style="background-color: #d4edda; padding: 15px; border-radius: 10px; border-left: 5px solid #28a745;">
            <h3 style="color: #155724; margin: 0;">📍 STEP 1: Apply Recommended Baseline</h3>
            <p style="color: #888; font-size: 0.85em; margin: 4px 0 0;">Goal: {diagnostic_goal}</p>
            <p style="color: #155724; font-size: 1.1em; margin-top: 10px;">
                <b>AI Smart Synthesis:</b><br>{st.session_state['current_baseline']}
            </p>
        </div>
    """, unsafe_allow_html=True)

    # --- STEP 2: REFINEMENT ---
    st.markdown("---")
    st.markdown("### 🛠️ STEP 2: Refine Image Quality")
    user_feedback = st.text_area(
        "Describe the issue:",
        height=150,
        placeholder="e.g., 'Bone looks too washed out' or 'Image is flat and gray, no contrast between structures'..."
    )

    if st.button("Analyze Image Issue"):
        if user_feedback:
            with st.spinner("Running differential diagnosis..."):

                prompt = f"""
                <knowledge_base>{knowledge_context}</knowledge_base>

                Task: Troubleshoot image quality for {software} | {machine}.
                Hardware Specs: {hardware_context}
                Diagnostic Goal: {diagnostic_goal}
                Current Baseline: {st.session_state['current_baseline']}
                User Feedback: {user_feedback}

                MANDATORY REASONING PROTOCOL — Follow ALL steps in order:

                STEP 1 — SENSOR SATURATION CHECK (from sensor_model.txt):
                  Based on hardware_context, is sensor saturation possible?
                  If YES: State this first. Software changes will not help if data is clipped.
                  If NO: Proceed to Step 2.

                STEP 2 — DIFFERENTIAL DIAGNOSIS (from differential_diagnosis.txt):
                  Map user feedback to the closest symptom category (A through G).
                  Run the disambiguation questions for that symptom.
                  State the most probable root cause (hardware or software).

                STEP 3 — ESCALATION LADDER (from differential_diagnosis.txt):
                  Start at Tier 1 (hardware). Only escalate if lower tier cannot fix it.
                  State which tier you are operating at.

                STEP 4 — PARAMETER INTERACTION CHECK (from sensor_model.txt Section 5):
                  Verify your recommended changes do not create an unsafe combination.
                  If a conflict exists, flag it and choose a safe alternative.

                STEP 5 — SUCCESS CRITERIA REFERENCE (from success_criteria.txt):
                  State which diagnostic structures the recommended fix will improve visibility of.
                  If the image will still be diagnostically inadequate after the fix, say so.

                STRICT CONSTRAINTS:
                1. PHYSICS: Whites are Radiopaque (dense bone/enamel). Blacks are Radiolucent.
                2. LAST RESORT ONLY: Suggest Contrast/Brightness ONLY if all other tiers fail.
                3. ALL adjustments in 5-10% increments. No jumps > 20% unless image is "unusable."
                4. FORMAT:
                   - Sensor Check: [Safe / Saturation Risk — explain]
                   - Diagnosis: [Symptom category + most probable root cause]
                   - Tier: [Which escalation tier]
                   - Actions: [Direct list: 'Parameter: Change from X to Y']
                   - Structures Improved: [Which success criteria structures this targets]
                   - Risk Flag: [Any parameter interaction warnings]

                LOG_ISSUE: [Concise tag]
                LOG_SETTINGS: [Settings string]
                """

                try:
                    response = client.messages.create(
                        model=HAIKU_MODEL,
                        max_tokens=1000,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    full_text = response.content[0].text

                    # Parse log tags
                    main_advice = []
                    log_issue = "general"
                    log_settings = "none"

                    for line in full_text.split('\n'):
                        if "LOG_ISSUE:" in line:
                            log_issue = line.split("LOG_ISSUE:")[1].strip()
                        elif "LOG_SETTINGS:" in line:
                            log_settings = line.split("LOG_SETTINGS:")[1].strip()
                        else:
                            main_advice.append(line)

                    st.session_state['current_ai_response'] = "\n".join(main_advice).strip()
                    st.session_state['standardized_issue'] = log_issue
                    st.session_state['formatted_settings'] = log_settings

                except Exception as e:
                    st.error(f"Analysis Error: {str(e)}")

    # --- 7. RESULTS & SUCCESS LOGGING ---
    if 'current_ai_response' in st.session_state:
        st.success(f"**Jazz AI Analysis:** \n\n {st.session_state['current_ai_response']}")

        st.divider()
        st.write("### 📝 Log Successful Calibration")

        tech_notes = st.text_input("Final Tech Notes (e.g., 'Client happy'):")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Log Success", use_container_width=True):
                with st.spinner("Logging..."):
                    success = log_to_google_sheets(
                        software,
                        machine,
                        st.session_state.get('standardized_issue', 'general'),
                        st.session_state.get('formatted_settings', 'none'),
                        tech_notes
                    )
                    if success:
                        st.toast("✅ Logged Successfully!")
                        clear_and_reset()
                        st.rerun()
        with col2:
            if st.button("🔄 Start Over", use_container_width=True):
                clear_and_reset()
                st.rerun()

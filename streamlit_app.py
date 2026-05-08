import streamlit as st
import pandas as pd
import anthropic
import os
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- 1. SETUP MODELS & CLIENT ---
# Using specific versioned IDs for maximum stability on Streamlit Cloud
SONNET_MODEL = "claude-sonnet-4-6"  # High-level synthesis for Baselines
HAIKU_MODEL = "claude-haiku-4-5"    # Rapid response for Troubleshooting 

try:
    client = anthropic.Anthropic(api_key=st.secrets["CLAUDE_KEY"])
except Exception:
    st.error("Missing CLAUDE_KEY in Streamlit Secrets!")
    st.stop()

# --- 2. DATA CONNECTIONS & HELPER FUNCTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_technical_manuals():
    """Reads external TXT files from the /knowledge directory"""
    paths = [
        "knowledge/quick_guide.txt", 
        "knowledge/settings_guide.txt",
        "knowledge/radiography_guide.txt"  # ADDED THIS
    ]
    combined_knowledge = ""
    for path in paths:
        if os.path.exists(path):
            with open(path, "r") as f:
                combined_knowledge += f"\n--- {path.upper()} ---\n{f.read()}\n"
    return combined_knowledge if combined_knowledge else "Technical manuals not found."

def clear_and_reset():
    """Clears session data for a fresh analysis"""
    keys_to_delete = ['current_ai_response', 'standardized_issue', 'formatted_settings', 'current_baseline', 'last_setup']
    for key in keys_to_delete:
        if key in st.session_state:
            del st.session_state[key]
    st.toast("System Reset")

def log_to_google_sheets(software, machine, issue, settings, notes):
    """Appends successful calibration data to Google Sheets"""
    try:
        # Read the current state of the sheet
        existing_data = conn.read()
        
        # Create a new row
        new_entry = pd.DataFrame([{
            "machine": machine,
            "software": software,
            "issue": issue,
            "settings": settings,
            "notes": notes if notes.strip() != "" else "none"
        }])
        
        # Append and update
        updated_df = pd.concat([existing_data, new_entry], ignore_index=True)
        conn.update(data=updated_df)
        
        # Clear cache so the next 'Smart Baseline' sees the new data
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"DATABASE ERROR: {e}")
        return False

def get_ai_baseline(software, machine, hardware_specs, df, knowledge):
    """Uses SONNET to synthesize a baseline from history and knowledge"""
    history = df[(df['software'] == software) & (df['machine'] == machine)]
    past_logs = history.tail(10).to_string(index=False) if not history.empty else "No history found."
    
    baseline_prompt = f"""
    You are a Senior Dental Imaging Specialist. 
    Synthesize a "Gold Standard" baseline for: {software} | {machine}.

    HARDWARE CONTEXT: {hardware_specs}
    KNOWLEDGE BASE: {knowledge}

    RADIOGRAPHY PHYSICS RULES:
    1. X-rays are negatives. RADIOPAQUE (dense/enamel/metal) = Whites. RADIOLUCENT (air/decay/pulp) = Blacks.
    2. CONTRAST/BRIGHTNESS RULE: Avoid adjusting Contrast or Brightness. Prioritize Gamma, CLAHE, and Adaptive Normalization. Only suggest Contrast/Brightness if standard tools cannot fix the exposure.

    Format: Return ONLY the settings list. Be extremely concise.
    """
    try:
        response = client.messages.create(
            model=SONNET_MODEL,
            max_tokens=600,
            messages=[{"role": "user", "content": baseline_prompt}]
        )
        return response.content[0].text.strip()
    except Exception as e:
        return f"Baseline Synthesis Unavailable (Error: {str(e)})"

# --- 3. LOAD DATA ---
knowledge_context = load_technical_manuals()
try:
    # We read the Google Sheet into a dataframe for the AI to analyze history
    df_history = conn.read()
except:
    df_history = pd.DataFrame(columns=['machine', 'software', 'issue', 'settings', 'notes'])

# --- 4. UI CONFIGURATION ---
st.set_page_config(page_title="Jazz AI Image Quality", page_icon="🦷")

# Custom styling for a cleaner look
st.markdown(
    """
    <style>
    div[data-testid="stTextArea"] textarea { background-color: #f0f2f6 !important; border: 1px solid #d1d5db !important; }
    blockquote { border-left: 5px solid #28a745 !important; background-color: #f9fafb !important; padding: 10px !important; }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🦷 Jazz AI Image Quality Assistant")

# --- 5. SIDEBAR: SETUP ---
st.sidebar.header("Initial Setup")
machine = st.sidebar.selectbox("X-ray Source", ["Select...", "Wall-mounted", "Hand-held"], index=0)

# Define options BEFORE the selectbox
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

# This variable is passed to the AI models
hardware_context = f"kVp: {kvp}, mA: {ma}, Exposure: {exposure}s"

st.sidebar.markdown("---") 
st.sidebar.caption("v1.0.3 | Jazz AI Support")

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
    # Trigger a new synthesis if the setup changed
    current_setup_id = f"{software}-{machine}"
    if 'current_baseline' not in st.session_state or st.session_state.get('last_setup') != current_setup_id:
        with st.spinner("AI is synthesizing a smart baseline from success history..."):
            st.session_state['current_baseline'] = get_ai_baseline(software, machine, df_history, knowledge_context)
            st.session_state['last_setup'] = current_setup_id

    st.markdown(f"""
        <div style="background-color: #d4edda; padding: 15px; border-radius: 10px; border-left: 5px solid #28a745;">
            <h3 style="color: #155724; margin: 0;">📍 STEP 1: Apply Recommended Baseline</h3>
            <p style="color: #155724; font-size: 1.1em; margin-top: 10px;">
                <b>AI Smart Synthesis:</b><br>{st.session_state['current_baseline']}
            </p>
        </div>
    """, unsafe_allow_html=True)

    # --- STEP 2: REFINEMENT ---
    st.markdown("---")
    st.markdown("### 🛠️ STEP 2: Refine Image Quality")
    user_feedback = st.text_area("Describe the issue:", height=150, placeholder="e.g., 'Shadows are too muddy'...")

if st.button("Analyze Image Issue"):
        if user_feedback:
            with st.spinner("Analyzing..."):
                prompt = f"""
                <knowledge_base>{knowledge_context}</knowledge_base>
                Task: Troubleshoot {software} | {machine}.
                Hardware Specs: {hardware_context}
                Current Baseline: {st.session_state['current_baseline']}
                User Feedback: {user_feedback}

                STRICT CONSTRAINTS:
                1. PHYSICS: Whites are Radiopaque (dense bone). Blacks are Radiolucent (empty air).
                2. SOFT CONSTRAINT: Only suggest changes to 'Contrast' or 'Brightness' as a LAST RESORT if Gamma, AN Percentiles, and CLAHE fail.
                3. DIRECT MODE: No conversational filler. Provide a quick summary of the cause, then recommended changes.
                4. FORMAT:
                   - Summary: [1 sentence cause]
                   - Actions: [Direct list: 'Parameter: Change from X to Y']
                   
                LOG_ISSUE: [Tag]
                LOG_SETTINGS: [Settings string]
                """
                
                try:
                    response = client.messages.create(
                        model=HAIKU_MODEL,
                        max_tokens=600,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    full_text = response.content[0].text
                    
                    # Parse tags for logging
                    main_advice = []
                    log_issue = "general"
                    log_settings = "none"
                    for line in full_text.split('\n'):
                        if "LOG_ISSUE:" in line: log_issue = line.split("LOG_ISSUE:")[1].strip()
                        elif "LOG_SETTINGS:" in line: log_settings = line.split("LOG_SETTINGS:")[1].strip()
                        else: main_advice.append(line)
                    
                    st.session_state['current_ai_response'] = "\n".join(main_advice).strip()
                    st.session_state['standardized_issue'] = log_issue
                    st.session_state['formatted_settings'] = log_settings
                except Exception as e:
                    st.error(f"Analysis Error: {str(e)}")

    # --- 7. DISPLAY RESULTS & SUCCESS LOGGING ---
    if 'current_ai_response' in st.session_state:
        st.success(f"**Jazz AI Analysis:** \n\n {st.session_state['current_ai_response']}")
        
        st.divider()
        st.write("### 📝 Log Successful Calibration")
        tech_notes = st.text_input("Final Tech Notes (e.g., 'Client very happy'):")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Log Success & Close Case", use_container_width=True):
                with st.spinner("Logging to database..."):
                    success = log_to_google_sheets(
                        software, 
                        machine, 
                        st.session_state.get('standardized_issue', 'general'), 
                        st.session_state.get('formatted_settings', 'none'), 
                        tech_notes
                    )
                    if success:
                        st.toast("✅ Log Saved!")
                        clear_and_reset()
                        st.rerun()
        with col2:
            if st.button("🔄 Start Over", use_container_width=True):
                clear_and_reset()
                st.rerun()
                

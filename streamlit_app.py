import streamlit as st
import pandas as pd
import anthropic
import os
import csv
from datetime import datetime

# --- 1. SETUP CLAUDE ---
try:
    client = anthropic.Anthropic(api_key=st.secrets["CLAUDE_KEY"])
except:
    st.error("Missing CLAUDE_KEY in Streamlit Secrets! Please add it to use the AI features.")

# --- 2. LOGGING & DATA LOADING LOGIC ---

def log_success(software, machine, issue, resolution):
    """Appends a successful resolution to a permanent CSV file."""
    log_file = "success_log.csv"
    # Note: Streamlit Cloud resets local files on reboot; 
    # for permanent storage, consider a database or GitHub API integration later.
    with open(log_file, mode='a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            software,
            machine,
            issue,
            resolution
        ])

def load_doc(filename):
    """Loads text manuals from the knowledge folder."""
    path = os.path.join("knowledge", filename)
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read()
    return "No specific manual found."

# Load text knowledge
settings_guide = load_doc("settings_guide.txt")
quick_guide = load_doc("quick_guide.txt")

# Load Baseline CSV
try:
    df_baseline = pd.read_csv("iq_settings.csv")
except:
    df_baseline = pd.DataFrame(columns=['machine', 'software', 'goal', 'details'])

# Load Success Log CSV
try:
    df_success = pd.read_csv("success_log.csv")
except:
    df_success = pd.DataFrame(columns=['Timestamp', 'Software', 'Machine', 'Issue', 'Resolution'])

# --- 3. UI CONFIGURATION ---
st.set_page_config(page_title="Jazz Sensor Assistant", page_icon="🦷")
st.title("🦷 Jazz Sensor Image Quality Assistant")

# --- 4. SIDEBAR: SETUP ---
st.sidebar.header("Initial Setup")

machine = st.sidebar.selectbox("X-ray Source", ["Wall-mounted", "Hand-held", "Unknown"])

# Categorized Software List (FUSE vs TWAIN)
software_options = sorted([
    "CDR DICOM", "Carestream", "Dentrix Ascend", "DEXIS", "Eaglesoft", "Sidexis", "Vixwin", # FUSE
    "XDR", "Edge Cloud", "Curve Hero", "Planmeca Romexis", "Oryx", "Tigerview", "Tracker", 
    "iDental", "Clio", "DTX Studio", "SOTA", "EzDent-i", "Open Dental", "Tab32", "SOPRO", 
    "Mipacs", "Denticon XV Capture", "Denticon XV Web", "CliniView", "Dentiray Capture", 
    "Imaging XL", "Prof. Suni", "Xray Vision", "SIGMA", "PatientGallery", "Xelis Dental", 
    "Overjet", "Aeka", "Other"
])
software = st.sidebar.selectbox("Imaging Software", software_options)

# --- 5. MAIN INTERFACE ---
st.write(f"### Current Baseline for {software}")

# Search for software baseline in CSV
match = df_baseline[df_baseline['software'] == software]
if not match.empty:
    baseline_details = match.iloc[0]['details']
    st.info(baseline_details)
else:
    baseline_details = "No baseline found. Use standard defaults."
    st.warning("No baseline found. Ask the assistant below for a starting point.")

st.divider()

# --- 6. INTERACTIVE TROUBLESHOOTING ---
st.write("### 💬 Refine Image Quality")

with st.form("ai_form"):
    user_feedback = st.text_input("Describe the issue (e.g., 'Image is grainy' or 'Suspected fracture'):")
    submit_button = st.form_submit_button("Analyze Image Issue")

if submit_button and user_feedback:
    with st.spinner("Consulting Jazz Knowledge Base & Success Logs..."):
        
        # Pull relevant history from Success Log
        past_fixes = ""
        if not df_success.empty:
            # Filter for this software and get the last 3 successful fixes
            history = df_success[df_success['Software'] == software].tail(3)
            if not history.empty:
                past_fixes = history[['Issue', 'Resolution']].to_string(index=False)

        prompt = f"""
        <system_instruction>
        You are the 'Jazz Sensor Technical Lead'. 
        Provide ONLY high-impact, technical troubleshooting steps.
        - Use the specific technical names and ranges from: {settings_guide}.
        - Apply specialty diagnostic logic from: {quick_guide}.
        - Format as: **Issue**, followed by a numbered list of **Actions**.
        - NO conversational filler.
        
        If available, consider these past successful fixes for this software:
        {past_fixes}
        </system_instruction>

        <context>
        Software: {software}
        X-ray Machine: {machine}
        Baseline Settings: {baseline_details}
        User Reported Issue: "{user_feedback}"
        </context>
        """
        
        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}]
            )
            
            ai_text = response.content[0].text
            st.session_state['last_ai_response'] = ai_text # Store for logging
            st.success(f"**Jazz Support AI:** \n\n {ai_text}")

        except Exception as e:
            st.error(f"Error contacting AI: {e}")

# --- 7. PERMANENT LOGGING BUTTON ---
# This sits outside the form so it doesn't trigger a re-analysis
if 'last_ai_response' in st.session_state:
    if st.button("🚀 This worked! Log success"):
        log_success(software, machine, user_feedback, st.session_state['last_ai_response'])
        st.toast("Success logged permanently to success_log.csv!")
        # Clear state to prevent double logging
        del st.session_state['last_ai_response']

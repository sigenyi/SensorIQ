import streamlit as st
import pandas as pd
import anthropic
import os
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# --- 1. SETUP CLAUDE ---
try:
    client = anthropic.Anthropic(api_key=st.secrets["CLAUDE_KEY"])
except:
    st.error("Missing CLAUDE_KEY in Streamlit Secrets!")

# --- 2. DATA CONNECTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def log_to_google_sheets(software, machine, issue, settings):
    """Appends success data using the same schema as iq_settings.csv"""
    new_entry = pd.DataFrame([{
        "machine": machine,
        "software": software,
        "issue": issue,
        "settings": settings,
        "notes": f"Logged via Assistant: {datetime.now().strftime('%Y-%m-%d')}"
    }])
    
    # Read existing data from Google Sheets
    try:
        existing_data = conn.read()
    except:
        existing_data = pd.DataFrame(columns=["machine", "software", "issue", "settings", "notes"])
        
    updated_df = pd.concat([existing_data, new_entry], ignore_index=True)
    conn.update(data=updated_df)

def clear_and_reset():
    """Clears inputs and session state to start fresh."""
    st.session_state.pop('current_ai_response', None)
    st.session_state.pop('last_issue', None)
    # Note: 'user_input' key is handled by the widget key assignment
    st.toast("System Reset - Parameters Cleared")

# --- 3. LOAD BASELINE DATA ---
try:
    df_baseline = pd.read_csv("iq_settings.csv")
except:
    df_baseline = pd.DataFrame(columns=['machine', 'software', 'issue', 'settings', 'notes'])

# --- 4. UI CONFIGURATION ---
st.set_page_config(page_title="Jazz Sensor Assistant", page_icon="🦷")
st.title("🦷 Jazz Sensor Image Quality Assistant")

# --- 5. SIDEBAR: SETUP ---
st.sidebar.header("Initial Setup")
machine = st.sidebar.selectbox("X-ray Source", ["Wall-mounted", "Hand-held"])

software_options = sorted([
    "CDR DICOM", "Carestream", "Dentrix Ascend", "DEXIS", "Eaglesoft", "Sidexis", "Vixwin", 
    "XDR", "Edge Cloud", "Curve Hero", "Planmeca Romexis", "Oryx", "Tigerview", "Tracker", 
    "iDental", "Clio", "DTX Studio", "SOTA", "EzDent-i", "Open Dental", "Tab32", "SOPRO", 
    "Mipacs", "Denticon XV Capture", "Denticon XV Web", "CliniView", "Dentiray Capture", 
    "Imaging XL", "Prof. Suni", "Xray Vision", "SIGMA", "PatientGallery", "Xelis Dental", 
    "Overjet", "Aeka", "CLASSIC", "Archy", "Other"
])
software = st.sidebar.selectbox("Imaging Software", software_options)

# --- 6. BASELINE DISPLAY ---
# Match software and use "Unknown" as a fallback for the machine type
match = df_baseline[(df_baseline['software'] == software) & 
                    ((df_baseline['machine'] == machine) | (df_baseline['machine'] == "Unknown"))]

if not match.empty:
    current_settings = match.iloc[0]['settings']
    st.info(f"**Current Baseline:** {current_settings}")
else:
    current_settings = "Standard defaults."
    st.warning("No specific baseline found. Using generic defaults.")

st.divider()

# --- 7. TROUBLESHOOTING ---
st.write("### 💬 Refine Image Quality")

# Key='user_input' allows us to manipulate it later
user_feedback = st.text_input("Describe the issue:", key="user_input")

if st.button("Analyze Image Issue"):
    if user_feedback:
        with st.spinner("Analyzing..."):
            # Load text guides for AI context
            settings_guide = "knowledge/settings_guide.txt" # Define path
            quick_guide = "knowledge/quick_guide.txt"       # Define path
            
            prompt = f"""
            You are the 'Jazz Sensor Technical Lead'. 
            Provide high-impact troubleshooting actions.
            
            Software: {software}
            Machine: {machine}
            Current Baseline: {current_settings}
            Issue: {user_feedback}
            """
            
            try:
                response = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=600,
                    messages=[{"role": "user", "content": prompt}]
                )
                st.session_state['current_ai_response'] = response.content[0].text
                st.session_state['last_issue'] = user_feedback
            except Exception as e:
                st.error(f"Error: {e}")

# --- 8. RESULTS & LOGGING ---
if 'current_ai_response' in st.session_state:
    st.success(f"**Jazz Support AI:** \n\n {st.session_state['current_ai_response']}")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ This worked! Log success"):
            log_to_google_sheets(
                software, 
                machine, 
                st.session_state['last_issue'], 
                st.session_state['current_ai_response']
            )
            clear_and_reset()
            st.rerun() 
    with col2:
        if st.button("🔄 Clear & Start Over"):
            clear_and_reset()
            st.rerun()

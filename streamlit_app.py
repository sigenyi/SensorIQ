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
# Connect to Google Sheets for permanent logging
conn = st.connection("gsheets", type=GSheetsConnection)

def log_to_google_sheets(software, machine, issue, resolution):
    """Appends data using the same column names as iq_settings.csv"""
    new_entry = pd.DataFrame([{
        "machine": machine,
        "software": software,
        "issue": issue,      # Now matches the column name
        "settings": resolution, # We rename 'resolution' to 'settings' to match
        "notes": datetime.now().strftime("%Y-%m-%d") # Use notes for the date
    }])
    
    existing_data = conn.read()
    updated_df = pd.concat([existing_data, new_entry], ignore_index=True)
    conn.update(data=updated_df)

def clear_and_reset():
    """Clears AI response and input to start from zero."""
    for key in ['current_ai_response', 'last_issue', 'user_input']:
        if key in st.session_state:
            del st.session_state[key]
    st.toast("System Reset - Parameters Cleared")

# Load baseline CSV
try:
    df_baseline = pd.read_csv("iq_settings.csv")
except:
    df_baseline = pd.DataFrame(columns=['machine', 'software', 'goal', 'details'])

# --- 3. UI CONFIGURATION ---
st.set_page_config(page_title="Jazz Sensor Assistant", page_icon="🦷")
st.title("🦷 Jazz Sensor Image Quality Assistant")

# --- 4. SIDEBAR: SETUP ---
st.sidebar.header("Initial Setup")

# "Unknown" removed from UI as requested
machine_options = ["Wall-mounted", "Hand-held"]
machine = st.sidebar.selectbox("X-ray Source", machine_options)

software_options = sorted([
    "CDR DICOM", "Carestream", "Dentrix Ascend", "DEXIS", "Eaglesoft", "Sidexis", "Vixwin", 
    "XDR", "Edge Cloud", "Curve Hero", "Planmeca Romexis", "Oryx", "Tigerview", "Tracker", 
    "iDental", "Clio", "DTX Studio", "SOTA", "EzDent-i", "Open Dental", "Tab32", "SOPRO", 
    "Mipacs", "Denticon XV Capture", "Denticon XV Web", "CliniView", "Dentiray Capture", 
    "Imaging XL", "Prof. Suni", "Xray Vision", "SIGMA", "PatientGallery", "Xelis Dental", 
    "Overjet", "Aeka", "Classic", "Archy", "Other"
])
software = st.sidebar.selectbox("Imaging Software", software_options)

# --- 5. BASELINE DISPLAY ---
# Logic still looks for "Unknown" in the CSV if the specific source isn't found
match = df_baseline[(df_baseline['software'] == software) & 
                    ((df_baseline['machine'] == machine) | (df_baseline['machine'] == "Unknown"))]

if not match.empty:
    baseline_details = match.iloc[0]['details']
    st.info(f"**Baseline Settings:** {baseline_details}")
else:
    baseline_details = "Standard defaults."
    st.warning("No specific baseline found for this combination.")

st.divider()

# --- 6. TROUBLESHOOTING ---
st.write("### 💬 Refine Image Quality")

# Use session state for the text input to allow clearing
user_feedback = st.text_input("Describe the issue:", key="user_input")

if st.button("Analyze Image Issue"):
    if user_feedback:
        with st.spinner("Analyzing..."):
            # Prompt logic remains the same (pointing to your knowledge docs)
            prompt = f"Software: {software} | Machine: {machine} | Issue: {user_feedback}"
            
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

# --- 7. RESULTS & RESET ---
if 'current_ai_response' in st.session_state:
    st.success(f"**Jazz Support AI:** \n\n {st.session_state['current_ai_response']}")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ This worked! Log success"):
            log_to_google_sheets(software, machine, st.session_state['last_issue'], st.session_state['current_ai_response'])
            clear_and_reset()
            st.rerun() # Refresh page to show clean state
    with col2:
        if st.button("🔄 Clear & Start Over"):
            clear_and_reset()
            st.rerun()

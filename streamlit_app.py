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
# Initialize connection with ttl=0 to disable caching (ensures live updates)
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
    
    # 1. Read current data using the explicit URL from secrets
    sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    existing_data = conn.read(spreadsheet=sheet_url)
    
    # 2. Append the new row
    updated_df = pd.concat([existing_data, new_entry], ignore_index=True)
    
    # 3. Push back to Google Sheets
    conn.update(spreadsheet=sheet_url, data=updated_df)
    
    # 4. Clear cache to ensure the next session sees the updated sheet
    st.cache_data.clear()

def clear_and_reset():
    """Clears AI response and input to start from zero."""
    if 'current_ai_response' in st.session_state:
        del st.session_state['current_ai_response']
    if 'last_issue' in st.session_state:
        del st.session_state['last_issue']
    # 'user_input' is handled by the widget key
    st.toast("System Reset - Parameters Cleared")

# --- 3. LOAD BASELINE DATA ---
try:
    df_baseline = pd.read_csv("iq_settings.csv")
except:
    df_baseline = pd.DataFrame(columns=['machine', 'software', 'issue', 'settings', 'notes'])

# --- 4. UI CONFIGURATION ---
st.set_page_config(page_title="Jazz Sensor Assistant", page_icon="🦷")

# --- CUSTOM STYLING ---
st.markdown(
    """
    <style>
    div[data-testid="stTextInput"] input {
        background-color: #e7e5f5 !important; /* Very light purple */
        border: 2px solid #ce93d8 !important; /* Defined border */
        color: #4a148c !important; /* Deep purple text */
    }
    </style>
    """,
    unsafe_allow_html=True
)

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
user_feedback = st.text_area(""How do you want to refine the image?", height=130, placeholder="e.g., The image is still too grainy in the posterior...")

if st.button("Analyze Image Issue"):
    if user_feedback:
        with st.spinner("Analyzing..."):
            # Load text guides for AI context
            settings_guide = "knowledge/settings_guide.txt" # Define path
            quick_guide = "knowledge/quick_guide.txt"       # Define path

            # Determine if the software belongs to the Apteryx family
            apteryx_software = ["Dentiray", "Harmony", "Imaging XL", "Denticon XV Capture", "Denticon XV Web"]
            is_apteryx = any(brand.lower() in software.lower() for brand in apteryx_software)
            
            prompt = f"""
            <task>
            Provide technical sensor calibration steps for: {software} | {machine}.
            Baseline: {current_settings}
            User Issue: {user_feedback}
            </task>

            <constraints>
            - Format ONLY as: **Issue**, followed by a numbered list of **Actions**.
            - NO intro, NO headers, NO "Root Cause", NO "Verification", NO titles.
            - NO conversational filler.
            - Be extremely brief.

            # 1. APTERYX SPECIFIC LOGIC
            {"- APTERYX DEVICE DETECTED: Note that values are REVERSED (higher % = more data cut off)." if is_apteryx else ""}
            {"- APTERYX LIMITS: Adaptive Normalization (0-100%), Despeckle (3x3-15x15), Laplace (3x3-15x15, Level 0-100), Gamma (0-100)." if is_apteryx else ""}

            # 2. HISTOGRAM & EXPOSURE RULES
            - IF Adaptive Normalization is adjusted: The AI must specify the level of peaks or dips to remove based on the recommended %. 
             *Example: "Adjust Normalization to 2% and verify histogram peaks below 240 to confirm brightness reduction.."*
            - ALWAYS provide recommended exposure times depending on the X-ray source.
             *Example: "Recommended Exposure: Anterior (0.08s - 0.10s) | Posterior (0.12s - 0.15s)".

            # 3. HANDHELD & PHYSICAL RULES
            - IF Machine includes 'Handheld' or 'Gun': Mandatory Step: "Remind client to maintain the EXACT same distance from the X-ray handgun to the patient as used during this calibration."
            - IF 'grainy' or 'pixelated': Add step to suggest zooming out to 1:1 or standing 3 feet back as the picture is magnified.
            - FINAL STEP (Suggestion only): Suggest physical baseline (70kVp/7mA/0.10s) if refinement of image is complex.
            </constraints>

            <example_format>
            **Issue**: Image too dark.
            1. Change Gamma from 0.65 to 0.90.
            2. Change Brightness from -0.05 to +0.10.
            3. Set S-Curve to 0.30.
            4. Keep in mind the image is magnified. Zoom out to 1:1 size or stand 3 feet back to check diagnostic quality.
            5. If issue persists, verify 70kVp/7mA/0.10s and cone-to-ring alignment.
            </example_format>
            """
            # ------------------------------------------

            try:
                response = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=300, # Tightened limit to save tokens
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
    
    # Use variables to hold the state so the button doesn't lose them on click
    current_res = st.session_state['current_ai_response']
    current_issue = st.session_state.get('last_issue', "General Issue")

    with col1:
        if st.button("✅ This worked! Log success", key="log_btn"):
            # 1. Run the function first
            try:
                log_to_google_sheets(software, machine, current_issue, current_res)
                # 2. If successful, then clear and rerun
                st.success("Data sent!") 
                clear_and_reset()
                st.rerun()
            except Exception as e:
                st.error(f"❌ LOGGING FAILED: {e}")
                st.stop()
                
    with col2:
        if st.button("🔄 Clear & Start Over", key="clear_btn"):
            clear_and_reset()
            st.rerun()

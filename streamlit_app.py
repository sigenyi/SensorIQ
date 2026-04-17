import streamlit as st
import pandas as pd
import anthropic
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- 1. SETUP CLAUDE ---
try:
    client = anthropic.Anthropic(api_key=st.secrets["CLAUDE_KEY"])
except Exception:
    st.error("Missing CLAUDE_KEY in Streamlit Secrets!")
    st.stop()

# --- 2. DATA CONNECTIONS & FUNCTIONS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def clear_and_reset():
    """Clears all session data to start a fresh analysis"""
    keys_to_delete = ['current_ai_response', 'last_issue', 'standardized_issue', 'formatted_settings']
    for key in keys_to_delete:
        if key in st.session_state:
            del st.session_state[key]
    st.toast("System Reset - Parameters Cleared")

def log_to_google_sheets(software, machine, issue, settings, notes):
    """Appends data to GSheets in the production format"""
    try:
        existing_data = conn.read()
        final_notes = notes if notes.strip() != "" else "none"
        
        new_entry = pd.DataFrame([{
            "machine": machine,
            "software": software,
            "issue": issue,
            "settings": settings,
            "notes": final_notes
        }])
        
        updated_df = pd.concat([existing_data, new_entry], ignore_index=True)
        conn.update(data=updated_df)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"DATABASE ERROR: {e}")
        return False

# --- 3. LOAD BASELINE DATA ---
try:
    df_baseline = pd.read_csv("iq_settings.csv")
except:
    df_baseline = pd.DataFrame(columns=['machine', 'software', 'issue', 'settings', 'notes'])

# --- 4. UI CONFIGURATION ---
st.set_page_config(page_title="Jazz AI Image quality", page_icon="🦷")

st.markdown(
    """
    <style>
    div[data-testid="stTextArea"] textarea { background-color: #e7e5f5 !important; border: 2px solid #ce93d8 !important; color: #4a148c !important; }
    div[data-testid="stTextInput"] input { background-color: #e7e5f5 !important; border: 2px solid #ce93d8 !important; color: #4a148c !important; }
    blockquote { border-left: 5px solid #ce93d8 !important; background-color: #f8f9fa !important; padding: 10px 15px !important; color: #4a148c !important; border-radius: 4px; }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🦷 Jazz AI Image Quality Assistant")

# --- 5. SIDEBAR: SETUP ---
st.sidebar.header("Initial Setup")
machine = st.sidebar.selectbox("X-ray Source", ["Wall-mounted", "Hand-held"])

software_options = sorted([
    "CDR DICOM", "Carestream", "Dentrix Ascend", "DEXIS", "Eaglesoft", "Sidexis", "Vixwin", 
    "XDR", "Edge Cloud", "Curve Hero", "Planmeca Romexis", "Oryx", "Tigerview", "Tracker", 
    "iDental", "Clio", "DTX Studio", "SOTA", "EzDent-i", "Open Dental", "Tab32", "SOPRO", 
    "Mipacs", "Denticon XV Capture", "Denticon XV Web", "CliniView", "Dentiray Capture", 
    "Imaging XL", "Prof. Suni", "Xray Vision", "SIGMA", "PatientGallery", "Xelis Dental", 
    "Overjet", "Aeka", "CLASSIC", "Archy", "OTHER", "Harmony"
])
software = st.sidebar.selectbox("Imaging Software", software_options)

# --- 6. BASELINE DISPLAY ---
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
user_feedback = st.text_area("How do you want to refine the image?", height=130, placeholder="e.g., The image is still too grainy...")

if st.button("Analyze Image Issue"):
    if user_feedback:
        with st.spinner("Analyzing..."):
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
            - NO intro, NO conversational filler.
            - Be extremely brief.

            # 1. APTERYX SPECIFIC LOGIC
            {"- APTERYX DEVICE DETECTED: Note that values are REVERSED (higher % = more data cut off)." if is_apteryx else ""}
            {"- APTERYX LIMITS: Adaptive Normalization (0-100%), Despeckle (3x3-15x15), Laplace (3x3-15x15, Level 0-100), Gamma (0-100)." if is_apteryx else ""}

            # 2. THE "CONTRAST" RULES (COLOR/STYLING)
            - Use standard numbering (1, 2, 3) for all numerical software/filter adjustments.
            - **IMPORTANT**: Any steps regarding "Zooming out", "Handheld distance", "Exposure times", or "Physical Baselines" MUST be prefixed with the `>` character. 

            # 3. HISTOGRAM & EXPOSURE RULES
            - IF Adaptive Normalization is adjusted: The AI must specify the level of removal based on the recommended 1–50% removal value of peaks or dips.
             *Example (Peaks): "Adjust Adaptive Normalization to remove the highest 2% of histogram peaks to confirm brightness reduction.."*
             *Example (Dips): "Adjust Adaptive Normalization to remove the lowest 3% of histogram dips and verify shadow noise reduction.."*
            - ALWAYS provide recommended exposure times depending on the X-ray source.

            # 4. HANDHELD & PHYSICAL RULES
            - IF Machine includes 'Handheld': Mandatory Step: "Remind client to maintain the EXACT same distance from the X-ray handgun to the patient as used during this calibration."
            - IF 'grainy' or 'pixelated': Suggest zooming out to 1:1 or standing 3 feet back as the picture is magnified.
            - FINAL STEP: Suggest physical baseline (70kVp/7mA/0.10s) if refinement is complex.

            # 5. DATA EXTRACTION (FOR THE SPREADSHEET ONLY)
            At the very bottom of your response, provide two hidden tags:
            LOG_ISSUE: [Standardized category: dark xray, bright xray, grainy xray, low contrast, distorted, underexposed, overexposed, foggy, static, blury, fuzzy, light, ghosting, or pixelated]
            LOG_SETTINGS: [Formatted exactly like this example: "Feature: Enabled (Param: Value, Param: Value), Feature: Enabled (Param: Value)"]
            </constraints>
            """

            try:
                response = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=500, # Tightened limit to save tokens
                    messages=[{"role": "user", "content": prompt}]
                )
                full_text = response.content[0].text
                
                # Split the text: Technician Advice vs Data for Spreadsheet
                main_advice = []
                log_issue = "general issue"
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
                st.session_state['last_issue'] = user_feedback
                    
            except Exception as e:
                st.error(f"Error: {e}")

# --- 8. RESULTS & LOGGING ---
if 'current_ai_response' in st.session_state:
    st.success(f"**Jazz Support AI Advice:** \n\n {st.session_state['current_ai_response']}")
    
    st.divider()
    st.write("### 📝 Finalize Log Entry")
    tech_notes = st.text_input("Add technician notes (optional):", placeholder="none")

    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✅ Log Success", key="log_btn"):
            with st.spinner("Logging..."):
                success = log_to_google_sheets(
                    software, 
                    machine, 
                    st.session_state.get('standardized_issue', 'general issue'), 
                    st.session_state.get('formatted_settings', 'none'), 
                    tech_notes
                )
                if success:
                    st.toast("✅ Logged Successfully!")
                    clear_and_reset()
                    st.rerun()
                
    with col2:
        if st.button("🔄 Clear & Start Over", key="clear_btn"):
            clear_and_reset()
            st.rerun()

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

# This adds spacing to push the button down (optional but looks cleaner)
st.sidebar.markdown("---") 

# THE FEEDBACK BUTTON
st.sidebar.link_button("🚀 Submit Feedback", "https://www.notion.so/jazzsupport/345f0a2e8ff5807d8f24d9a86bf4e742?v=345f0a2e8ff58080ae22000c286546a3&source=copy_link", use_container_width=True)

# --- 6. BASELINE DISPLAY ---
st.divider()

# Match software and machine
match = df_baseline[(df_baseline['software'] == software) & 
                    ((df_baseline['machine'] == machine) | (df_baseline['machine'] == "Unknown"))]

if not match.empty:
    current_settings = match.iloc[0]['settings']
    # ATTENTION GRABBER: Recommended Baseline
    st.markdown(f"""
        <div style="background-color: #d4edda; padding: 15px; border-radius: 10px; border-left: 5px solid #28a745;">
            <h3 style="color: #155724; margin: 0;">📍 STEP 1: Apply Recommended Baseline</h3>
            <p style="color: #155724; font-size: 1.1em; margin-top: 10px;">
                <b>Try these settings first:</b><br>{current_settings}
            </p>
            <p style="color: #155724; font-size: 0.9em;">
                <i>If the image still isn't perfect, move to Step 2 below to refine it.</i>
            </p>
        </div>
    """, unsafe_allow_html=True)
else:
    current_settings = "Standard defaults."
    # ATTENTION GRABBER: No Baseline
    st.markdown("""
        <div style="background-color: #fff3cd; padding: 15px; border-radius: 10px; border-left: 5px solid #ffc107;">
            <h3 style="color: #856404; margin: 0;">⚠️ No Baseline Found</h3>
            <p style="color: #856404; font-size: 1.1em; margin-top: 10px;">
                We don't have a saved baseline for this setup yet.
            </p>
            <p style="color: #856404; font-size: 1.1em; font-weight: bold;">
                👉 START HERE: Use the 'Refine Image' box below to describe the current image, and AI will help you build the first baseline.
            </p>
        </div>
    """, unsafe_allow_html=True)

st.write("") # Spacer

# --- 7. TROUBLESHOOTING ---
st.markdown("---") # Visual break from Step 1
st.markdown("### 🛠️ STEP 2: Refine Image Quality")

# Use a subtle info box for instructions so they don't get lost in the scroll
st.info("💡 **Instructions:** If the baseline settings above aren't perfect, describe the visual issue below. Claude will provide specific adjustment steps.")

# The actual input area
user_feedback = st.text_area(
    label="Describe the image issue:", 
    height=150, 
    placeholder="e.g., 'The posterior images are too dark' or 'The anterior is grainy'...",
    help="Be as specific as possible (e.g., mention specific tooth areas or software filters)."
)

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
            - IF Adaptive Normalization is adjusted: Always provide Low Percentile, High Percentile recomendations along with the level of removal based on the recommended removal value of peaks or dips.
             *Example (Peaks): "Adjust Adaptive Normalization to Low Percentile 0, High Percentile 2 remove the highest 2% of histogram peaks to confirm brightness reduction.."*
             *Example (Dips): "Adjust Adaptive Normalization to Low Percentile 3, High Percentile 100 remove the lowest 3% of histogram dips and verify shadow noise reduction.."*
            - ALWAYS provide recommended exposure times depending on the X-ray source.
             *Example: "Recommended Exposure: Anterior (0.08s - 0.10s) | Posterior (0.12s - 0.15s)".

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

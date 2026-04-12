import streamlit as st
import pandas as pd
import anthropic
import os

# --- 1. SETUP CLAUDE ---
try:
    client = anthropic.Anthropic(api_key=st.secrets["CLAUDE_KEY"])
except:
    st.error("Missing CLAUDE_KEY in Streamlit Secrets! Please add it to use the AI features.")

# --- 2. DOCUMENT LOADING LOGIC ---
def load_doc(filename):
    path = os.path.join("knowledge", filename)
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read()
    return "No specific manual uploaded yet. Use general expert knowledge."

# Load your future documents (Placeholders for now)
settings_guide = load_doc("settings_guide.txt")
quick_guide = load_doc("quick_guide.txt")

# Load the CSV memory
try:
    df = pd.read_csv("iq_settings.csv")
except:
    st.error("Missing iq_settings.csv")

st.set_page_config(page_title="Jazz Sensor Assistant", page_icon="🦷")
st.title("🦷 Jazz Sensor Image Quality Assistant")

# --- SIDEBAR: SETUP ---
st.sidebar.header("Initial Setup")
machine = st.sidebar.selectbox("X-ray Source", ["Wall-mounted", "Hand-gun"])
software = st.sidebar.selectbox("Imaging Software", ["Dexis 10", "Schick 5", "Apteryx", "VixWin"])

# --- MAIN INTERFACE ---
st.write(f"### Current Baseline for {software}")
match = df[df['software'] == software]
if not match.empty:
    baseline = match.iloc[0]['details']
    st.info(baseline)
else:
    st.info("No baseline found. Ask the assistant below for a starting point.")

st.divider()

# --- INTERACTIVE TROUBLESHOOTING ---
st.write("### 💬 Refine Image Quality")
user_feedback = st.text_input("Describe the issue (e.g., 'The image is too dark', 'It looks grainy')")

if user_feedback:
    with st.spinner("Consulting Jazz Sensor Knowledge Base..."):
        prompt = f"""
        You are the 'Jazz Sensor Image Quality Assistant'. 
        Reference these guides if available:
        Guide 1: {settings_guide}
        Guide 2: {quick_guide}
        
        The technician is using {software} and a {machine}.
        The feedback is: "{user_feedback}".
        
        Provide a concise, professional recommendation for the technician to improve the image.
        """
        
        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001", # Updated to the latest model
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}]
            )
            st.success(f"**Jazz Support AI:** \n\n {response.content[0].text}")
        except Exception as e:
            st.error(f"Could not connect to AI. Check your API key and credits. Error: {e}")

        if st.button("🚀 This worked! Log success"):
            st.toast("Success logged! The system is learning.")

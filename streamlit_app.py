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

# Use a form to prevent accidental re-runs
with st.form("ai_form"):
    user_feedback = st.text_input("Describe the issue:")
    submit_button = st.form_submit_button("Analyze Issue")

if submit_button and user_feedback:
    with st.spinner("Consulting Jazz Sensor Knowledge Base..."):
        prompt = f"""
        <system_instruction>
        You are the 'Dentistry XRAY Sensor Technical Lead'. 
        Provide ONLY high-impact, technical imaging troubleshooting steps. 
        - Base recommendations on standardized radiologic principles.
        - DO NOT include conversational filler, intros, or "Quick Tips".
        - DO NOT include follow-up questions.
        - Format as: **Issue**, followed by a numbered list of **Actions**.
        - Use specific technical names from: {settings_guide} and {quick_guide}.
        </system_instruction>

        <context>
        Software: {software} | X-ray: {machine}
        Issue: "{user_feedback}"
        </context>
        """
        
        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=500, # Increased so it doesn't cut off mid-sentence
                messages=[{"role": "user", "content": prompt}]
            )
            st.success(f"**Jazz Support AI:** \n\n {response.content[0].text}")
        except Exception as e:
            st.error(f"Error: {e}")

        if st.button("🚀 This worked! Log success"):
            st.toast("Success logged! The system is learning.")

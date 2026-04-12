import streamlit as st
import pandas as pd

# Load the memory - pointing to your new file name
try:
    df = pd.read_csv("iq_settings.csv")
except:
    st.error("Could not find the 'iq_settings.csv' file! Make sure it is in the same folder on GitHub.")

st.set_page_config(page_title="SensorIQ", page_icon="🦷")
st.title("🦷 SensorIQ: Dental Imaging Support")

# User Inputs
st.sidebar.header("Current Setup")
machine = st.sidebar.selectbox("X-ray Source", ["Wall-mounted", "Hand-gun"])
software = st.sidebar.selectbox("Imaging Software", ["Dexis", "Schick", "Apteryx", "VixWin"])
goal = st.sidebar.selectbox("Desired Outcome", ["Higher Sharpness", "Clearer Bone", "Lower Noise"])

# Search Logic
st.subheader("💡 Recommended Settings")
# This looks through your CSV for a match
match = df[(df['machine'] == machine) & (df['software'] == software) & (df['goal'] == goal)]

if not match.empty:
    result = match.iloc[0]
    st.info(f"**Try these settings:** \n\n {result['details']}")
    
    # Simple feedback button
    if st.button("✅ This worked!"):
        st.balloons()
        st.success("Great! This success has been noted.")
else:
    st.warning("No specific recommendation found yet for this combination. Try a different goal or wait for the Claude update!")

st.divider()
st.caption("Step 4 is next: Deploying to the web.")

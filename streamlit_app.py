import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="SensorIQ", page_icon="🦷")
st.title("🦷 Jazz Sensor Image Quality Assistant")

# --- DEBUGGING SECTION ---
# This part helps us see what files are actually there
if not os.path.exists("iq_settings.csv"):
    st.error("⚠️ I still can't find 'iq_settings.csv'.")
    st.write("Files I can see in the folder:", os.listdir("."))
    st.stop() # This stops the app before it crashes
# -------------------------

# Load the memory
df = pd.read_csv("iq_settings.csv")

# User Inputs
st.sidebar.header("Current Setup")
machine = st.sidebar.selectbox("X-ray Source", ["Wall-mounted", "Hand-gun"])
software = st.sidebar.selectbox("Imaging Software", ["Dexis", "Schick", "Apteryx", "VixWin"])
goal = st.sidebar.selectbox("Desired Outcome", ["Higher Sharpness", "Clearer Bone", "Lower Noise"])

# Search Logic
st.subheader("💡 Recommended Settings")
match = df[(df['machine'] == machine) & (df['software'] == software) & (df['goal'] == goal)]

if not match.empty:
    result = match.iloc[0]
    st.info(f"**Try these settings:** \n\n {result['details']}")
    
    if st.button("✅ This worked!"):
        st.balloons()
        st.success("Great! This success has been noted.")
else:
    st.warning("No specific recommendation found yet. Try a different setup!")

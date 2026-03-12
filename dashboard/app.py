import streamlit as st

st.set_page_config(
    page_title="Strategic Watch AI",
    page_icon="🌍",
    layout="wide",
)

st.title("🌍 Strategic Watch AI")
st.subheader("AI-Powered Geopolitical Intelligence Dashboard")

st.markdown(
    """
This is a **simplified version** of the Strategic Watch AI dashboard used for debugging.

If you can see this text and the sidebar, the basic UI is working.
"""
)

with st.sidebar:
    st.header("Settings")
st.write("Use the controls below to confirm the basic UI is responding.")

clicked = st.button("Test button – you should see a message when this is clicked")

st.write(f"Clicked flag (for debugging): {clicked}")

if clicked:
    st.success("Test button clicked – the app is responding correctly.")


import requests
import streamlit as st

st.set_page_config(page_title="AI Customer Agent Dashboard", layout="wide")
st.title("AI Customer Agent")
st.caption("Grounded KB + appointment booking + LangGraph orchestration")

if "session_id" not in st.session_state:
    st.session_state["session_id"] = ""

api_url = st.sidebar.text_input("API URL", value="http://127.0.0.1:8000")

col1, col2 = st.columns([2, 1])

with col1:
    q = st.text_area("User message", placeholder="Ask a DL question or request appointment booking.", height=120)
    if st.button("Send") and q.strip():
        try:
            payload = {"session_id": st.session_state["session_id"] or None, "message": q}
            r = requests.post(f"{api_url}/chat", json=payload, timeout=60)
            r.raise_for_status()
            data = r.json()
            st.session_state["session_id"] = data.get("session_id", st.session_state["session_id"])
            st.subheader("Answer")
            st.write(data.get("answer", ""))
            st.caption(
                f"Intent: {data.get('intent')} | Refusal: {data.get('refusal')} | Similarity: {data.get('best_similarity')}"
            )
            st.subheader("Sources")
            st.json(data.get("sources", []))
        except Exception as e:
            st.error(f"API error: {e}")

with col2:
    st.subheader("Session")
    st.text_input("Session ID", value=st.session_state["session_id"], disabled=True)
    if st.button("Reset Session"):
        st.session_state["session_id"] = ""
        st.success("Session reset.")

    st.subheader("Appointment Slots")
    service_type = st.selectbox("Service Type", ["", "dl_appointment", "state_id", "renewal"])
    if st.button("Refresh Slots"):
        try:
            params = {"service_type": service_type} if service_type else {}
            r = requests.get(f"{api_url}/appointments/slots", params=params, timeout=20)
            r.raise_for_status()
            st.json(r.json())
        except Exception as e:
            st.error(f"Slots error: {e}")

    st.subheader("KB Operations")
    if st.button("Ingest / Rebuild Index"):
        try:
            r = requests.post(f"{api_url}/ingest", timeout=300)
            r.raise_for_status()
            st.success("Ingest complete")
            st.json(r.json())
        except Exception as e:
            st.error(f"Ingest error: {e}")

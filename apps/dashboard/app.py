import requests
import streamlit as st

st.set_page_config(page_title="civicflow_agent_demo Dashboard", layout="wide")
st.title("civicflow_agent_demo")
st.caption("Continuous chat with grounded KB + appointments")


def _init_state() -> None:
    st.session_state.setdefault("session_id", "")
    st.session_state.setdefault("messages", [])


def _meta_caption(meta: dict) -> str:
    intent = meta.get("intent")
    refusal = meta.get("refusal")
    sim = meta.get("best_similarity")
    return f"Intent: {intent} | Refusal: {refusal} | Similarity: {sim}"


_init_state()

api_url = st.sidebar.text_input("API URL", value="http://127.0.0.1:8000")

with st.sidebar:
    st.subheader("Session")
    st.text_input("Session ID", value=st.session_state["session_id"], disabled=True)
    if st.button("New Conversation"):
        st.session_state["session_id"] = ""
        st.session_state["messages"] = []
        st.rerun()

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


for message in st.session_state["messages"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        meta = message.get("meta") or {}
        if message["role"] == "assistant" and meta:
            st.caption(_meta_caption(meta))
            sources = meta.get("sources") or []
            if sources:
                with st.expander("Sources"):
                    st.json(sources)


prompt = st.chat_input("Ask about DL/ID services or appointments")
if prompt:
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                payload = {"session_id": st.session_state["session_id"] or None, "message": prompt}
                r = requests.post(f"{api_url}/chat", json=payload, timeout=60)
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                msg = f"API error: {e}"
                st.error(msg)
                st.session_state["messages"].append({"role": "assistant", "content": msg, "meta": {}})
            else:
                st.session_state["session_id"] = data.get("session_id", st.session_state["session_id"])
                answer = data.get("answer", "")
                meta = {
                    "intent": data.get("intent"),
                    "refusal": data.get("refusal"),
                    "best_similarity": data.get("best_similarity"),
                    "sources": data.get("sources", []),
                }
                st.markdown(answer)
                st.caption(_meta_caption(meta))
                if meta["sources"]:
                    with st.expander("Sources"):
                        st.json(meta["sources"])
                st.session_state["messages"].append(
                    {"role": "assistant", "content": answer, "meta": meta}
                )

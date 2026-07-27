import streamlit as st
import requests
import uuid

st.set_page_config(
    page_title="Ticket Triage Agent Dashboard",
    page_icon="🎫",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------- Configuration --------------------
BACKEND_URL = st.sidebar.text_input("Backend API URL", value="http://127.0.0.1:8000")

# -------------------- Custom CSS --------------------
st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        border: 1px solid #e9ecef;
        margin-bottom: 10px;
    }
    .system-log {
        font-family: 'Courier New', Courier, monospace;
        background-color: #1e1e1e;
        color: #d4d4d4;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
    }
    .info-box {
        background-color: #e7f3fe;
        border-left: 6px solid #2196F3;
        padding: 10px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# -------------------- Helper Functions --------------------
def check_backend_health():
    try:
        r = requests.get(f"{BACKEND_URL}/health", timeout=2)
        return r.status_code == 200
    except Exception:
        return False

def display_system_messages(messages):
    """Render system logs in a pretty format."""
    if not messages:
        st.caption("No system logs yet.")
        return
    for m in messages:
        role = m.get("role")
        content = m.get("content", "")
        if role == "system":
            if "[Classifier]" in content:
                st.markdown("**🏷️ Classifier**")
                st.code(content, language="bash")
            elif "[Sufficiency Check]" in content:
                st.markdown("**🔍 Sufficiency Check**")
                if "✅" in content:
                    st.success(content)
                else:
                    st.warning(content)
            elif "[Router]" in content:
                st.markdown("**🔀 Router**")
                st.code(content, language="bash")
            elif "[HITL]" in content:
                st.markdown("**👥 Human-in-the-Loop**")
                st.info(content)
            else:
                st.text(content)
        elif role == "assistant" and "TICKET REVIEW REQUIRED" in content:
            st.markdown("**📋 Human Review Summary**")
            st.code(content, language="text")
        elif role == "user":
            st.markdown("**👤 User Clarification**")
            st.chat_message("user").write(content)

def render_ticket(ticket, is_past=False):
    """
    Display ticket details, logs, and (if not past) interactive action buttons.
    """
    if not ticket:
        st.info("No ticket selected.")
        return

    # --- Top Metrics ---
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Ticket ID", ticket.get("ticket_id", "N/A"))
    with col2:
        cat = ticket.get("category", "general").upper()
        st.metric("Category", cat)
    with col3:
        urg = ticket.get("urgency", "low").upper()
        st.metric("Urgency", urg)
    with col4:
        stage = ticket.get("stage", "N/A").replace("_", " ").upper()
        st.metric("Stage", stage)

    # --- Main Layout ---
    left_col, right_col = st.columns([3, 2])

    with left_col:
        # ---------- Ticket Details ----------
        with st.expander("📄 Ticket Details", expanded=True):
            st.markdown("**Raw Ticket Text**")
            st.text_area(
                "Raw Ticket",
                value=ticket.get("raw_ticket", ""),
                height=100,
                disabled=True,
                label_visibility="collapsed"
            )
            if ticket.get("summary"):
                st.markdown(f"**Summary:** {ticket['summary']}")
            if ticket.get("keywords"):
                st.markdown(f"**Keywords:** {', '.join(ticket['keywords'])}")
            if ticket.get("assigned_person"):
                st.markdown(f"**Assigned To:** {ticket['assigned_person']} ({ticket.get('assigned_team', '')})")
                st.markdown(f"**Contact Email:** {ticket.get('contact_email', 'N/A')}")
            if ticket.get("created_at"):
                st.markdown(f"**Created:** {ticket['created_at']}")

        # ---------- Interactive Actions (only for current ticket) ----------
        if not is_past:
            stage = ticket.get("stage")
            if stage == "needs_clarification":
                st.info("💡 **More context required.** The agent needs additional information.")
                st.subheader("Clarifying Questions")
                questions = ticket.get("clarifying_questions", [])
                if questions:
                    for idx, q in enumerate(questions, 1):
                        st.markdown(f"**{idx}.** {q}")
                else:
                    st.caption("No specific questions were formulated.")

                clarification_input = st.text_area(
                    "Your response:",
                    value=st.session_state.get("clarification_input", ""),
                    placeholder="Provide details answering the above queries...",
                    key="clarification_text_area",
                    height=100,
                    on_change=lambda: st.session_state.update(
                        clarification_input=st.session_state.clarification_text_area
                    )
                )
                if st.button("Submit Clarification", type="primary"):
                    if not clarification_input.strip():
                        st.warning("Please provide some clarification.")
                    else:
                        with st.spinner("Sending clarification..."):
                            try:
                                response = requests.post(
                                    f"{BACKEND_URL}/ticket/clarify",
                                    json={
                                        "thread_id": st.session_state.thread_id,
                                        "clarification": clarification_input
                                    }
                                )
                                if response.status_code == 200:
                                    st.session_state.current_ticket = response.json()
                                    st.session_state.clarification_input = ""
                                    st.rerun()
                                else:
                                    st.error(f"Error: {response.text}")
                            except Exception as e:
                                st.error(f"Connection Error: {str(e)}")

            elif stage == "awaiting_human_approval":
                st.warning("🚧 **Human-in-the-Loop Intercept.** The agent is waiting for your authorization.")
                st.markdown("### 📋 Routing Decision")
                st.markdown(f"""
                - **Assigned Professional**: `{ticket.get('assigned_person', 'Unassigned')}`
                - **Team**: `{ticket.get('assigned_team', 'Unassigned')}`
                - **Contact**: `{ticket.get('contact_email', 'Unassigned')}`
                - **Urgency**: `{ticket.get('urgency', '').upper()}`
                """)
                if ticket.get("summary"):
                    st.info(f"**Summary:** {ticket['summary']}")
                st.markdown("---")
                feedback = st.text_input(
                    "Feedback / Change Instructions (optional)",
                    placeholder="Why reject? Provide override instructions."
                )
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("✅ Approve", type="primary", use_container_width=True):
                        with st.spinner("Approving..."):
                            try:
                                response = requests.post(
                                    f"{BACKEND_URL}/ticket/approve",
                                    json={
                                        "thread_id": st.session_state.thread_id,
                                        "approved": True,
                                        "feedback": feedback
                                    }
                                )
                                if response.status_code == 200:
                                    st.session_state.current_ticket = response.json()
                                    st.rerun()
                            except Exception as e:
                                st.error(str(e))
                with col_b:
                    if st.button("❌ Reject / Reclassify", use_container_width=True):
                        with st.spinner("Rejecting..."):
                            try:
                                response = requests.post(
                                    f"{BACKEND_URL}/ticket/approve",
                                    json={
                                        "thread_id": st.session_state.thread_id,
                                        "approved": False,
                                        "feedback": feedback or "Incorrect classification."
                                    }
                                )
                                if response.status_code == 200:
                                    st.session_state.current_ticket = response.json()
                                    st.rerun()
                            except Exception as e:
                                st.error(str(e))

            elif stage in ["approved", "routed"]:
                st.success("🎉 **Triage Successfully Executed!**")
                st.markdown(f"""
                The ticket has been authorized and dispatched.
                - **Ticket ID**: `{ticket.get('ticket_id')}`
                - **Assigned Team**: `{ticket.get('assigned_team')}`
                - **Point of Contact**: `{ticket.get('assigned_person')}`
                - **Contact**: `{ticket.get('contact_email')}`
                """)
                if st.button("📊 View Ticket Flow"):
                    flow_url = f"{BACKEND_URL}/ticket/flow/{st.session_state.thread_id}"
                    st.markdown(f'<iframe src="{flow_url}" width="100%" height="600"></iframe>', unsafe_allow_html=True)
                if st.button("Start Fresh Ticket", type="primary"):
                    for key in ["thread_id", "current_ticket", "clarification_input"]:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.rerun()

            elif stage == "rejected":
                st.warning("❌ **Routing was rejected.** The ticket will be re‑classified with your feedback.")
                st.info(f"Feedback: {ticket.get('human_feedback', 'No feedback provided.')}")
                st.markdown("The system will now re‑run the classification pipeline. Please wait...")
                if st.button("🔄 Refresh Status"):
                    try:
                        r = requests.get(f"{BACKEND_URL}/ticket/status/{st.session_state.thread_id}")
                        if r.status_code == 200:
                            st.session_state.current_ticket = r.json()
                            st.rerun()
                    except Exception as e:
                        st.error(str(e))

            else:
                st.info(f"⏳ Processing: stage `{stage}`. The system is working. Please wait or refresh.")
                if st.button("🔄 Refresh Status"):
                    try:
                        r = requests.get(f"{BACKEND_URL}/ticket/status/{st.session_state.thread_id}")
                        if r.status_code == 200:
                            st.session_state.current_ticket = r.json()
                            st.rerun()
                    except Exception as e:
                        st.error(str(e))
        else:
            # Past tickets – show a summary of the outcome
            if ticket.get("stage") in ["approved", "routed"]:
                st.success("✅ This ticket was successfully triaged and dispatched.")
            elif ticket.get("stage") == "rejected":
                st.warning("❌ This ticket was rejected by the human reviewer.")
            else:
                st.info(f"Final stage: {ticket.get('stage')}")

            if ticket.get("thread_id"):
                if st.button("📊 View Ticket Flow", key=f"flow_{ticket.get('thread_id')}"):
                    flow_url = f"{BACKEND_URL}/ticket/flow/{ticket.get('thread_id')}"
                    st.markdown(f'<iframe src="{flow_url}" width="100%" height="600"></iframe>', unsafe_allow_html=True)

    # -------------------- Right Column: Logs --------------------
    with right_col:
        st.subheader("⚙️ System Audit Logs")
        with st.expander("Show detailed logs", expanded=True):
            display_system_messages(ticket.get("messages", []))

# -------------------- Sidebar --------------------
st.sidebar.title("🤖 Multi-Agent Triage")
st.sidebar.subheader("Connection Status")
backend_alive = check_backend_health()
if backend_alive:
    st.sidebar.success("FastAPI Backend: CONNECTED")
else:
    st.sidebar.error("FastAPI Backend: DISCONNECTED")
    st.sidebar.info("Ensure server is running: `uvicorn server:app --reload --port 8000`")

# View selector
view = st.sidebar.radio(
    "View",
    ["Current Ticket", "Past Tickets"],
    index=0 if st.session_state.get("view", "Current Ticket") == "Current Ticket" else 1
)
if view != st.session_state.get("view"):
    st.session_state.view = view
    if view == "Current Ticket":
        st.session_state.selected_past_thread = None
        st.session_state.past_ticket_data = None
    st.rerun()

if st.sidebar.button("🔄 Reset Current Session", use_container_width=True):
    for key in ["thread_id", "current_ticket", "clarification_input", "selected_past_thread", "past_ticket_data"]:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state.view = "Current Ticket"
    st.rerun()

st.sidebar.subheader("📝 Pre-loaded Test Cases")
demo_tickets = {
    "Vague App Outage (Triggers Loop)": "The app is completely broken and nothing works.",
    "Database Crash (Direct Route)": "Production database is down. Getting 'Error 1040: Too many connections' continuously right now.",
    "Login Feature Failure": "I am experiencing a 500 error when attempting to hit the login endpoint '/api/v1/auth/login' on Chrome.",
    "Billing Inconsistency": "My credit card was charged twice for our corporate service subscription this month. Need refund."
}
selected_demo = st.sidebar.selectbox("Choose a template", ["None"] + list(demo_tickets.keys()))

# -------------------- Main Interface --------------------
st.title("🎫 Support Ticket Triage Dashboard")
st.markdown("An agentic workflow built with **LangGraph** & **Ollama (Llama 3.2)** to automatically classify, clarify, route, and supervise company support tickets.")

# Initialize session state variables
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None
if "current_ticket" not in st.session_state:
    st.session_state.current_ticket = None
if "clarification_input" not in st.session_state:
    st.session_state.clarification_input = ""
if "view" not in st.session_state:
    st.session_state.view = "Current Ticket"
if "selected_past_thread" not in st.session_state:
    st.session_state.selected_past_thread = None
if "past_ticket_data" not in st.session_state:
    st.session_state.past_ticket_data = None

# -------------------- View Handling --------------------
if st.session_state.view == "Current Ticket":
    # ----- Current Ticket -----
    if st.session_state.thread_id is None:
        # New ticket submission
        st.subheader("Step 1: Submit a Support Ticket")
        default_text = demo_tickets.get(selected_demo) if selected_demo != "None" else ""
        ticket_input = st.text_area(
            "Describe your technical problem or issue in detail:",
            value=default_text,
            placeholder="Paste log traces, describe symptoms, app name, when it started...",
            height=150
        )
        if st.button("Submit Ticket", type="primary", disabled=not backend_alive):
            if not ticket_input.strip():
                st.warning("Please enter some ticket text first.")
            else:
                with st.spinner("Analyzing and initiating agentic triage flow..."):
                    try:
                        response = requests.post(
                            f"{BACKEND_URL}/ticket/new",
                            json={"ticket_text": ticket_input}
                        )
                        if response.status_code == 200:
                            data = response.json()
                            st.session_state.thread_id = data["thread_id"]
                            st.session_state.current_ticket = data
                            st.rerun()
                        else:
                            st.error(f"Error starting pipeline: {response.text}")
                    except Exception as e:
                        st.error(f"API Connection Exception: {str(e)}")
    else:
        # Active ticket – render with interactive actions
        ticket = st.session_state.current_ticket
        if not ticket:
            st.error("No ticket data found. Please reset and try again.")
            if st.button("Reset"):
                st.session_state.thread_id = None
                st.session_state.current_ticket = None
                st.rerun()
            st.stop()
        render_ticket(ticket, is_past=False)

else:
    # ----- Past Tickets -----
    st.subheader("📂 Past Tickets")
    try:
        response = requests.get(f"{BACKEND_URL}/tickets?limit=20")
        if response.status_code == 200:
            tickets = response.json()
        else:
            st.error("Failed to fetch past tickets.")
            tickets = []
    except Exception as e:
        st.error(f"Error: {str(e)}")
        tickets = []

    if not tickets:
        st.info("No past tickets found.")
    else:
        # Show a table
        for t in tickets:
            cols = st.columns([3, 2, 2, 1])
            cols[0].write(f"**{t.get('ticket_id', 'N/A')}**")
            cols[1].write(f"{t.get('stage', '')}")
            cols[2].write(f"{t.get('state', {}).get('category', '')} / {t.get('state', {}).get('urgency', '')}")
            if cols[3].button("View", key=f"view_{t.get('thread_id')}"):
                # Fetch full state
                try:
                    r = requests.get(f"{BACKEND_URL}/ticket/full/{t.get('thread_id')}")
                    if r.status_code == 200:
                        full_ticket = r.json()
                        st.session_state.selected_past_thread = t.get('thread_id')
                        st.session_state.past_ticket_data = full_ticket
                        st.rerun()
                    else:
                        st.error("Failed to load ticket details.")
                except Exception as e:
                    st.error(str(e))

        # If a past ticket is selected, show its details
        if st.session_state.past_ticket_data:
            st.markdown("---")
            st.subheader(f"Ticket Details: {st.session_state.past_ticket_data.get('ticket_id', '')}")
            render_ticket(st.session_state.past_ticket_data, is_past=True)
            if st.button("Close Details"):
                st.session_state.selected_past_thread = None
                st.session_state.past_ticket_data = None
                st.rerun()
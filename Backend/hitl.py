from state import TicketState
from routing_db import URGENCY_SLA


def prepare_human_review(state: TicketState) -> TicketState:
    """
    This node prepares a human-readable summary for approval.
    The graph interrupts BEFORE this node so the human sees it
    before any action is taken.
    """
    urgency = state.get("urgency", "medium")
    sla = URGENCY_SLA.get(urgency, "")

    summary = (
        f"TICKET REVIEW REQUIRED\n"
        f"─────────────────────────────\n"
        f"Ticket ID  : {state.get('ticket_id', 'N/A')}\n"
        f"Category   : {state.get('category', '—').upper()}\n"
        f"Urgency    : {state.get('urgency', '—').upper()}\n"
        f"SLA        : {sla}\n"
        f"Summary    : {state.get('summary', '—')}\n"
        f"Keywords   : {', '.join(state.get('keywords', []))}\n"
        f"─────────────────────────────\n"
        f"Assigned To: {state.get('assigned_person', '—')}\n"
        f"Team       : {state.get('assigned_team', '—')}\n"
        f"Contact    : {state.get('contact_email', '—')}\n"
        f"─────────────────────────────\n"
        f"Please review the above and approve or reject the routing decision."
    )
    visited = state.get("visited_nodes", [])
    visited.append("prepare_review")

    return {
        **state,
        "stage": "awaiting_human_approval",
        "visited_nodes": visited,
        "messages": state.get("messages", []) + [
            {"role": "assistant", "content": summary}
        ],
    }


def apply_human_decision(state: TicketState) -> TicketState:
    """Called after human provides approve/reject feedback."""
    approved = state.get("human_approved", False)
    feedback = state.get("human_feedback", "")

    if approved:
        msg = f"[HITL] Human approved routing. Ticket dispatched to {state.get('assigned_person')}."
    else:
        msg = f"[HITL] Human rejected routing. Feedback: {feedback}. Ticket returned for re-classification."

    visited = state.get("visited_nodes", [])
    visited.append("apply_decision")

    return {
        **state,
        "visited_nodes": visited,
        "stage": "approved" if approved else "rejected",
        "messages": state.get("messages", []) + [{"role": "system", "content": msg}],
    }
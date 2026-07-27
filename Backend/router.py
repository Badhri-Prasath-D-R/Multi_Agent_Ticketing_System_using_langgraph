from state import TicketState
from routing_db import ROUTING_DB, URGENCY_SLA


def route_ticket(state: TicketState) -> TicketState:
    category = state.get("category", "general")
    urgency = state.get("urgency", "medium")

    route = ROUTING_DB.get(category, ROUTING_DB["general"])
    sla = URGENCY_SLA.get(urgency, URGENCY_SLA["medium"])

    msg = (
        f"[Router] Assigned to: {route['person']} ({route['team']}) "
        f"| Contact: {route['email']} | SLA: {sla}"
    )
    visited = state.get("visited_nodes", [])
    visited.append("route")

    return {
        **state,
        "assigned_team": route["team"],
        "assigned_person": route["person"],
        "contact_email": route["email"],
        "stage": "routed",
        "visited_nodes": visited,
        "messages": state.get("messages", []) + [{"role": "system", "content": msg}],
    }
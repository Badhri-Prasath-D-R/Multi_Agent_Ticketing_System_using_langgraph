import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from state import TicketState
from classifier import classify_ticket
from sufficiency_checker import check_sufficiency
from router import route_ticket
from hitl import prepare_human_review, apply_human_decision

def route_after_sufficiency(state: TicketState) -> str:
    if state.get("is_sufficient"):
        return "route"
    return "needs_clarification"


def route_after_human(state: TicketState) -> str:
    if state.get("human_approved"):
        return "done"
    return "reclassify"

def build_graph():
    builder = StateGraph(TicketState)

    builder.add_node("classify",        classify_ticket)
    builder.add_node("check_sufficiency", check_sufficiency)
    builder.add_node("route",           route_ticket)
    builder.add_node("prepare_review",  prepare_human_review)
    builder.add_node("apply_decision",  apply_human_decision)

    builder.set_entry_point("classify")

    builder.add_edge("classify", "check_sufficiency")

    builder.add_conditional_edges(
        "check_sufficiency",
        route_after_sufficiency,
        {
            "route":              "route",
            "needs_clarification": END,   
        },
    )

    builder.add_edge("route", "prepare_review")

    builder.add_edge("prepare_review", "apply_decision")

    builder.add_conditional_edges(
        "apply_decision",
        route_after_human,
        {
            "done":       END,
            "reclassify": "classify",   
        },
    )

    memory = MemorySaver()
    return builder.compile(
        checkpointer=memory,
        interrupt_before=["apply_decision"], 
    )

graph = build_graph()
"""
FastAPI server exposing the ticket triage agent over HTTP.
Run: uvicorn server:app --reload --port 8000
"""
import sys, os, uuid
sys.path.insert(0, os.path.dirname(__file__))
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from db import save_ticket_state
from db import tickets_collection
import networkx as nx
from pyvis.network import Network
from fastapi.responses import HTMLResponse 
from datetime import datetime
import logging

from graph import graph

app = FastAPI(title="Ticket Triage Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions: dict = {}

class NewTicketRequest(BaseModel):
    ticket_text: str

class ClarificationRequest(BaseModel):
    thread_id: str
    clarification: str

class ApprovalRequest(BaseModel):
    thread_id: str
    approved: bool
    feedback: Optional[str] = ""


def _serialize(state: dict) -> dict:
    """Return only UI-relevant fields."""
    return {
        "thread_id": state.get("_thread_id"),
        "ticket_id": state.get("ticket_id"),
        "raw_ticket": state.get("raw_ticket"),   # <-- add this
        "stage": state.get("stage"),
        "category": state.get("category"),
        "created_at": state.get("created_at"),
        "urgency": state.get("urgency"),
        "summary": state.get("summary"),
        "keywords": state.get("keywords", []),
        "is_sufficient": state.get("is_sufficient"),
        "clarifying_questions": state.get("clarifying_questions", []),
        "assigned_person": state.get("assigned_person"),
        "assigned_team": state.get("assigned_team"),
        "contact_email": state.get("contact_email"),
        "messages": state.get("messages", []),
        "clarification_count": state.get("clarification_count", 0),
    }

@app.post("/ticket/new")
def new_ticket(req: NewTicketRequest):
    """Submit a new ticket and kick off the pipeline."""
    ticket_id = f"TKT-{uuid.uuid4().hex[:6].upper()}"
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    state = {
        "ticket_id": ticket_id,
        "raw_ticket": req.ticket_text,
        "created_at": datetime.utcnow().isoformat(),
        "messages": [],
        "human_approved": None,
        "human_feedback": None,
        "user_clarification": None,
        "category": None, "urgency": None,
        "summary": None, "keywords": None,
        "is_sufficient": None, "clarifying_questions": None,
        "assigned_team": None, "assigned_person": None,
        "contact_email": None, "stage": None,
    }

    result = graph.invoke(state, config)
    result["_thread_id"] = thread_id
    sessions[thread_id] = (result, config)
    save_ticket_state(result, result.get("stage", "new"))   # <-- store
    return _serialize(result)


@app.post("/ticket/clarify")
def clarify(req: ClarificationRequest):
    if req.thread_id not in sessions:
        return {"error": "Session not found"}

    result, config = sessions[req.thread_id]
    result["user_clarification"] = req.clarification
    # 🔥 Increment count
    result["clarification_count"] = result.get("clarification_count", 0) + 1
    result["stage"] = "reclassifying"

    result = graph.invoke(result, config)
    result["_thread_id"] = req.thread_id
    sessions[req.thread_id] = (result, config)
    save_ticket_state(result, result.get("stage", "clarified")) 
    return _serialize(result)


@app.post("/ticket/approve")
def approve(req: ApprovalRequest):
    if req.thread_id not in sessions:
        return {"error": "Session not found"}

    result, config = sessions[req.thread_id]
    result["human_approved"] = req.approved
    result["human_feedback"] = req.feedback or ""

    # Try to resume the graph
    result = graph.invoke(result, config)
    result["_thread_id"] = req.thread_id

    # If the graph did NOT advance (still waiting), force the decision
    if result.get("stage") == "awaiting_human_approval":
        logging.warning(f"Graph did not resume for thread {req.thread_id}. Forcing {'approval' if req.approved else 'rejection'}.")
        if req.approved:
            result["stage"] = "approved"
            result["visited_nodes"] = result.get("visited_nodes", []) + ["apply_decision"]
            result["messages"] = result.get("messages", []) + [
                {"role": "system", "content": f"[HITL] Human approved routing. Ticket dispatched to {result.get('assigned_person')}."}
            ]
        else:
            result["stage"] = "rejected"
            result["visited_nodes"] = result.get("visited_nodes", []) + ["apply_decision"]
            result["messages"] = result.get("messages", []) + [
                {"role": "system", "content": f"[HITL] Human rejected routing. Feedback: {req.feedback}. Ticket returned for re-classification."}
            ]
        # Clear human decision flags to avoid reusing them if reclassified later
        result["human_approved"] = None
        result["human_feedback"] = None

    # If the stage is "rejected", we already have the fallback reclassification logic – keep it
    if result.get("stage") == "rejected":
        logging.warning(f"Graph ended with rejected for thread {req.thread_id}. Forcing reclassification.")
        # Reset human flags and re-invoke to restart from classify
        result["human_approved"] = None
        result["human_feedback"] = None
        result["stage"] = "reclassifying"
        result = graph.invoke(result, config)
        result["_thread_id"] = req.thread_id

    sessions[req.thread_id] = (result, config)
    save_ticket_state(result, result.get("stage", "approved"))
    return _serialize(result)

@app.get("/ticket/status/{thread_id}")
def status(thread_id: str):
    if thread_id not in sessions:
        return {"error": "Session not found"}
    result, _ = sessions[thread_id]
    return _serialize(result)


@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/ticket/flow/{thread_id}")
def get_flow(thread_id: str):
    if thread_id not in sessions:
        return {"error": "Session not found"}
    state, _ = sessions[thread_id]
    visited = state.get("visited_nodes", [])

    G = nx.DiGraph()
    # Define all possible edges (from graph.py)
    edges = [
        ("classify", "check_sufficiency"),
        ("check_sufficiency", "route"),        # if sufficient
        ("check_sufficiency", "end"),          # if insufficient (clarification exit)
        ("route", "prepare_review"),
        ("prepare_review", "apply_decision"),
        ("apply_decision", "end"),             # if approved
        ("apply_decision", "classify"),        # if rejected (loop back)
    ]
    G.add_edges_from(edges)

    # Highlight visited nodes and edges
    net = Network(height="600px", width="100%", directed=True)
    for node in G.nodes:
        color = "#97c2fc" if node in visited else "#ddd"
        net.add_node(node, label=node, color=color, shape="box" if node in visited else "ellipse")
    for u, v in G.edges:
        # Check if this edge was traversed (both nodes in visited and consecutive in visited)
        traversed = False
        for i in range(len(visited)-1):
            if visited[i] == u and visited[i+1] == v:
                traversed = True
                break
        color = "green" if traversed else "gray"
        net.add_edge(u, v, color=color, width=2 if traversed else 1)

    # Return the HTML directly
    html = net.generate_html()
    return HTMLResponse(html)

@app.get("/tickets")
def list_tickets(limit: int = 20):
    """
    Return a list of recent tickets (summary) from MongoDB.
    """
    cursor = tickets_collection.find(
        {},
        {
            "_id": 0,
            "ticket_id": 1,
            "thread_id": 1,
            "stage": 1,
            "timestamp": 1,
            "state.category": 1,
            "state.urgency": 1,
            "state.assigned_person": 1,
            "state.assigned_team": 1,
            "state.summary": 1,
        }
    ).sort("timestamp", -1).limit(limit)
    tickets = list(cursor)
    return tickets

@app.get("/ticket/full/{thread_id}")
def get_full_ticket(thread_id: str):
    """
    Retrieve the complete state of a ticket by its thread_id.
    """
    doc = tickets_collection.find_one({"thread_id": thread_id}, {"_id": 0})
    if not doc:
        return {"error": "Ticket not found"}
    # The 'state' field contains the full TicketState
    return doc.get("state", {})
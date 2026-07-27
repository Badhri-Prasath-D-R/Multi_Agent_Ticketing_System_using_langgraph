import json
import re
from langchain_ollama import OllamaLLM
from state import TicketState

llm = OllamaLLM(model="llama3.2:3b", temperature=0.1)

SUFFICIENCY_PROMPT = """You are an IT support triage specialist. Evaluate whether this support ticket has enough information to act on.

Ticket: \"\"\"{ticket}\"\"\"
Category: {category}
Urgency: {urgency}

Decide if the ticket is sufficient. A ticket is sufficient if it includes:
1. Clear description of what the problem is (not just "it's broken")
2. When it started (e.g., "since yesterday", "after upgrade")
3. Who/what is affected (e.g., "all users", "specific app", "single department")
4. Any error messages, log excerpts, or specific symptoms
5. Impact (e.g., "blocked from working", "minor inconvenience")

Return ONLY valid JSON:
{{
  "is_sufficient": true or false,
  "reason": "<one line explaining your decision>",
  "clarifying_questions": ["<question1>", "<question2>"]
}}

If sufficient, clarifying_questions should be an empty list [].
If not sufficient, provide 2-3 specific, concrete questions that would help resolve the ticket.
Return ONLY JSON. No markdown."""
MAX_CLARIFICATION_ROUNDS = 3


def check_sufficiency(state: TicketState) -> TicketState:
    current_count = state.get("clarification_count", 0)
    ticket = state["raw_ticket"]
    if state.get("user_clarification"):
        ticket = ticket + "\n\nAdditional context: " + state["user_clarification"]

    if current_count >= MAX_CLARIFICATION_ROUNDS:
        msg = f"[Sufficiency Check] 🚨 Max clarification rounds reached ({MAX_CLARIFICATION_ROUNDS}). Forcing sufficiency to True."
        return {
            **state,
            "is_sufficient": True,
            "clarifying_questions": [],
            "clarification_count": current_count,
            "stage": "sufficiency_checked",
            "messages": state.get("messages", []) + [{"role": "system", "content": msg}]
        }
    
    response = llm.invoke(SUFFICIENCY_PROMPT.format(
    ticket=ticket,
    category=state.get("category", "general"),
    urgency=state.get("urgency", "medium"),
    ))

    clean = re.sub(r"```(?:json)?|```", "", response).strip()

    try:
        data = json.loads(clean)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", clean, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            data = {"is_sufficient": True, "reason": "Defaulting to sufficient", "clarifying_questions": []}

    is_sufficient = data.get("is_sufficient", True)
    questions = data.get("clarifying_questions", [])

    msg = f"[Sufficiency Check] {'✅ Sufficient' if is_sufficient else '⚠️ More info needed'} — {data.get('reason', '')}"

    visited = state.get("visited_nodes", [])
    visited.append("check_sufficiency")

    return {
        **state,
        "is_sufficient": is_sufficient,
        "clarifying_questions": questions,
        "stage": "needs_clarification" if not is_sufficient else "sufficient",
        "visited_nodes": visited,
        "messages": state.get("messages", []) + [{"role": "system", "content": msg}],
    }
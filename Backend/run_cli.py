"""
Interactive CLI for the Ticket Triage Multi-Agent System.
Run: python run_cli.py
"""
import sys, os, uuid
sys.path.insert(0, os.path.dirname(__file__))

from graph import graph

BANNER = """
╔══════════════════════════════════════════════════════╗
║       Ticket Triage Multi-Agent System               ║
║       Powered by LangGraph + Ollama llama3.2:3b      ║
╚══════════════════════════════════════════════════════╝
"""

def print_messages(messages: list, seen: set) -> set:
    for msg in messages:
        content = msg.get("content", "")
        role = msg.get("role", "")
        key = content[:80]
        if key not in seen:
            seen.add(key)
            if role == "system":
                print(f"\n  🔧 {content}")
            elif role == "assistant":
                print(f"\n{content}")
    return seen


def run():
    print(BANNER)
    ticket_text = input("Describe your issue (paste your support ticket):\n> ").strip()
    if not ticket_text:
        print("No ticket text provided. Exiting.")
        return

    ticket_id = f"TKT-{uuid.uuid4().hex[:6].upper()}"
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    state: dict = {
        "ticket_id": ticket_id,
        "raw_ticket": ticket_text,
        "messages": [],
        "human_approved": None,
        "human_feedback": None,
        "user_clarification": None,
        "category": None,
        "urgency": None,
        "summary": None,
        "keywords": None,
        "is_sufficient": None,
        "clarifying_questions": None,
        "assigned_team": None,
        "assigned_person": None,
        "contact_email": None,
        "stage": None,
    }

    seen_msgs: set = set()

    print(f"\nProcessing ticket {ticket_id}...\n")

    result = graph.invoke(state, config)
    seen_msgs = print_messages(result.get("messages", []), seen_msgs)

    while result.get("stage") == "needs_clarification":
        questions = result.get("clarifying_questions", [])
        print("\n❓ The agent needs more information...")
        for q in questions:
            print(f"  - {q}")
        clarification = input("\nPlease provide the requested details:\n> ").strip()
        if not clarification:
            clarification = "No additional information provided."

        # 🔥 Increment the clarification count
        result["clarification_count"] = result.get("clarification_count", 0) + 1
        result["user_clarification"] = clarification
        result["stage"] = "reclassifying"

        result = graph.invoke(result, config)
        seen_msgs = print_messages(result.get("messages", []), seen_msgs)

    while result.get("stage") == "awaiting_human_approval":
        print("\n" + "─" * 54)
        answer = input("\nDo you approve this routing decision? (yes/no): ").strip().lower()
        approved = answer in ("yes", "y")

        feedback = ""
        if not approved:
            feedback = input("Provide feedback / correction: ").strip()

        result["human_approved"] = approved
        result["human_feedback"] = feedback
        result = graph.invoke(result, config)
        seen_msgs = print_messages(result.get("messages", []), seen_msgs)

    stage = result.get("stage", "")
    print("\n" + "═" * 54)
    if stage == "approved":
        print(f"🎉 Ticket {ticket_id} successfully triaged and dispatched!")
        print(f"   → Assigned to : {result.get('assigned_person')} ({result.get('assigned_team')})")
        print(f"   → Contact     : {result.get('contact_email')}")
        print(f"   → Urgency     : {result.get('urgency', '').upper()}")
    elif stage == "rejected":
        print(f"Ticket {ticket_id} routing was rejected — please re-submit with corrections.")
    else:
        print(f"Ticket {ticket_id} processing ended at stage: {stage}")
    print("═" * 54 + "\n")


if __name__ == "__main__":
    run()
import json
import re
from langchain_ollama import OllamaLLM
from state import TicketState

llm = OllamaLLM(model="llama3.2:3b", temperature=0.1)

CLASSIFY_PROMPT = """You are a precise IT support ticket classifier. Analyze the ticket and return ONLY valid JSON, no explanation.

Ticket:
\"\"\"{ticket}\"\"\"

Classify into exactly this JSON structure:
{{
  "category": "<one of: network, software, hardware, security, database, access, billing, hr, general>",
  "urgency": "<one of: critical, high, medium, low>",
  "summary": "<one sentence summary of the core problem>",
  "keywords": ["<keyword1>", "<keyword2>", "<keyword3>"]
}}

Category guidelines:
- network: VPN, connectivity, DNS, firewall, latency
- software: application crashes, bugs, feature not working, API errors
- hardware: printer, laptop, server hardware, monitor, peripheral
- security: phishing, unauthorized access, data breach, virus
- database: query failures, connection pool, deadlocks, replication
- access: permissions, role changes, MFA, login issues
- billing: invoice, payment, subscription, refund
- hr: onboarding, payroll, benefits, employee queries
- general: anything not fitting above

Urgency rules:
- critical: system down, data breach, production outage, cannot work at all
- high: major feature broken, many users affected, deadline at risk
- medium: some functionality impaired, workaround exists
- low: minor issue, cosmetic, future request

Return ONLY the JSON object. No markdown, no explanation."""


def classify_ticket(state: TicketState) -> TicketState:
    ticket = state["raw_ticket"]
    if state.get("user_clarification"):
        ticket = ticket + "\n\nAdditional info from user: " + state["user_clarification"]

    response = llm.invoke(CLASSIFY_PROMPT.format(ticket=ticket))

    clean = re.sub(r"```(?:json)?|```", "", response).strip()

    try:
        data = json.loads(clean)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", clean, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            data = {
                "category": "general",
                "urgency": "medium",
                "summary": ticket[:120],
                "keywords": [],
            }
    
    visited = state.get("visited_nodes", [])
    visited.append("classify")

    return {
        **state,
        "category": data.get("category", "general"),
        "urgency": data.get("urgency", "medium"),
        "summary": data.get("summary", ""),
        "keywords": data.get("keywords", []),
        "stage": "classified",
        "visited_nodes": visited,
        "messages": state.get("messages", []) + [
            {"role": "system", "content": f"[Classifier] Category: {data.get('category')} | Urgency: {data.get('urgency')} | Summary: {data.get('summary')}"}
        ],
    }
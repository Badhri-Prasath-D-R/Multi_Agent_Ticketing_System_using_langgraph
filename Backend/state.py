from typing import TypedDict, Optional, List, Literal

class TicketState(TypedDict):
    ticket_id: str
    created_at: Optional[str]
    raw_ticket: str

    category: Optional[str]
    urgency: Optional[Literal["critical", "high", "medium", "low"]]
    summary: Optional[str]
    keywords: Optional[List[str]]
    is_sufficient: Optional[bool]
    clarifying_questions: Optional[List[str]]
    user_clarification: Optional[str]

    clarification_count: Optional[int]

    assigned_team: Optional[str]
    assigned_person: Optional[str]
    contact_email: Optional[str]

    human_approved: Optional[bool]
    human_feedback: Optional[str]

    stage: Optional[str]
    messages: List[dict]
    visited_nodes: Optional[List[str]]
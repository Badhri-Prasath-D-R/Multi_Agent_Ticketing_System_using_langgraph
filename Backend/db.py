import os
from pymongo import MongoClient
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise ValueError("MONGO_URI environment variable is not set. Please set it to your MongoDB Atlas connection string.")

client = MongoClient(MONGO_URI)
db = client["ticket_triage"]
tickets_collection = db["tickets"]

def save_ticket_state(state: dict, stage: str):
    """Insert or update the ticket document with the current state."""
    doc = {
        "ticket_id": state.get("ticket_id"),
        "thread_id": state.get("_thread_id"),
        "stage": stage,
        "state": state,
        "timestamp": datetime.utcnow()
    }
    tickets_collection.update_one(
        {"thread_id": state.get("_thread_id")},
        {"$set": doc},
        upsert=True
    )
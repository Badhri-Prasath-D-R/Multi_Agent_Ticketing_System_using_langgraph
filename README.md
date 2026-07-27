# Multi-Agent Ticketing System

A Python-based ticket triage platform that uses an LLM-powered workflow to classify support tickets, assess whether enough information is present, route them to the appropriate team, and involve a human reviewer before final dispatch.

The system combines a FastAPI backend, a Streamlit dashboard, and a LangGraph-based agent workflow to provide a complete end-to-end support ticket handling experience.

## Overview

This repository is designed to help teams automate the first stages of support operations:

1. Accept a new support ticket.
2. Classify it into a category and urgency level.
3. Determine whether the ticket has enough details to route safely.
4. Ask clarifying questions when information is incomplete.
5. Route the ticket to the right team/person using predefined routing rules.
6. Pause for human approval before final dispatch.
7. Store ticket state in MongoDB for later retrieval and review.

## Key Features

- LLM-assisted ticket classification
- Sufficiency checking for missing context
- Clarification loop for incomplete tickets
- Human-in-the-loop approval before routing
- Graph-based workflow orchestration with LangGraph
- REST API for integration
- Streamlit-based web dashboard
- Persistent ticket storage in MongoDB

## Architecture

### Backend

The backend is implemented in the Backend folder and contains the main workflow and API service:

- Backend/server.py: FastAPI server exposing ticket endpoints
- Backend/graph.py: LangGraph workflow definition
- Backend/classifier.py: Ticket classification using Ollama
- Backend/sufficiency_checker.py: Checks if the ticket is actionable
- Backend/router.py: Routes tickets to the appropriate team/person
- Backend/hitl.py: Creates the human-review approval flow
- Backend/db.py: Persists ticket state to MongoDB
- Backend/state.py: Shared typed state structure for the workflow
- Backend/run_cli.py: Interactive CLI for testing the workflow

### Frontend

The frontend is a Streamlit application in the Frontend folder:

- Frontend/app.py: Web dashboard for creating and reviewing tickets

## Tech Stack

- Python
- FastAPI
- Streamlit
- LangGraph
- LangChain Ollama integration
- MongoDB
- Pydantic
- NetworkX and PyVis

## Project Structure

```text
.
├── Backend/
│   ├── classifier.py
│   ├── db.py
│   ├── graph.py
│   ├── hitl.py
│   ├── router.py
│   ├── routing_db.py
│   ├── run_cli.py
│   ├── server.py
│   ├── state.py
│   └── sufficiency_checker.py
├── Frontend/
│   └── app.py
├── .gitignore
├── knowledge.md
└── README.md
```

## Prerequisites

Before running the project, ensure you have:

- Python 3.10+ installed
- Ollama installed and running locally
- An Ollama model available, preferably llama3.2:3b
- A MongoDB instance or MongoDB Atlas connection string

## Installation

Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate
```

On Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Install the required Python packages:

```bash
pip install fastapi uvicorn streamlit pymongo python-dotenv langgraph langchain-ollama networkx pyvis pydantic requests
```

## Environment Configuration

Create a .env file in the Backend folder with your MongoDB connection string:

```env
MONGO_URI=mongodb+srv://<username>:<password>@<cluster-url>/test?w=majority
```

Make sure Ollama is running and that the model is available:

```bash
ollama pull llama3.2:3b
```

## Running the Application

### 1. Start the backend API

From the Backend folder:

```bash
cd Backend
python -m uvicorn server:app --reload --port 8000
```

The API will be available at:

- http://127.0.0.1:8000/health

### 2. Start the Streamlit dashboard

From the Frontend folder:

```bash
cd Frontend
streamlit run app.py
```

The UI will open in your browser and allow you to submit and review tickets.

### 3. Run the CLI version

From the Backend folder:

```bash
cd Backend
python run_cli.py
```

This provides a terminal-based workflow for testing the classification and routing pipeline.

## API Endpoints

The FastAPI server exposes the following endpoints:

- POST /ticket/new: Create a new ticket and start the workflow
- POST /ticket/clarify: Send clarification details for an unresolved ticket
- POST /ticket/approve: Approve or reject the routing decision
- GET /ticket/status/{thread_id}: Fetch the current state of a ticket
- GET /health: Health check endpoint
- GET /ticket/flow/{thread_id}: Return a graph visualization of the workflow
- GET /tickets: List recently stored tickets
- GET /ticket/full/{thread_id}: Retrieve the full stored state for a ticket

### Example request

```bash
curl -X POST http://127.0.0.1:8000/ticket/new \
  -H "Content-Type: application/json" \
  -d '{"ticket_text":"My VPN disconnects every 20 minutes and I cannot access the internal tools."}'
```

## Workflow Behavior

The ticket processing flow is:

1. Classify the ticket
2. Check whether more information is needed
3. If insufficient, request clarification
4. Route the ticket to a team/person
5. Pause for human approval
6. Finalize the decision or reclassify based on feedback

## Notes

- Clarification rounds are capped to avoid endless loops.
- The routing rules are defined in Backend/routing_db.py.
- The human approval step is designed to keep the final routing decision under operator control.
- The project currently relies on a local Ollama setup for language model inference.

## Future Improvements

Possible enhancements for this project include:

- Adding authentication and authorization for the API
- Supporting more advanced routing logic
- Integrating a real database migration strategy
- Adding automated tests
- Replacing hardcoded routing mappings with a configurable rules engine

## License

No license has been specified for this repository yet.

> This section contains all the prompts for phase 4 of the project. LLM should not process this file.

# Architectural Strategy

Now that the multi-agent AI system has been implemented using Crew AI in phase 3, we will implement the On-Demand API . The `crewai-insight-service` microservice implementation must follow the "On-Demand" pattern explained below.

### 1. The "On-Demand" API (Asynchronous Execution)

* **Endpoint:** A `POST /api/v1/emails/summarize` endpoint handles manual triggers from the UI.
* **Asynchronicity:** Because AI processing may take a few seconds to several minutes, the service must return a `job_id` immediately and process the request in the background.
* **UI Integration:** The "Executive Dashboard" in the `email-reader-ui` will poll for the status of the `job_id` and fetch the completed reports.

### 2. Mindmap Visualization Strategy

* **Rendering:** Use a React-compatible visualization (such as D3.js as specified in Agent 6) to render the hierarchy.
* **Interactivity:** The visualization must be interactive, supporting click-to-expand nodes and hover-tooltips that display the full `insight` summary (State, Next Step, Owner, and Priority).
# Email Reader Console

This is the original console-based application created as a PoC for fetching and archiving emails from Outlook Web using Microsoft Graph API.

## Features
- Fetches the latest email from the inbox.
- Archives email metadata to a local JSON file in the `data/` directory.
- Logs activity in the `logs/` directory.
- Prevents duplicate archiving based on `messageId`.

## Setup

1.  **Environment Variables**: Create a `.env` file (you can use `.env.example` as a template) and provide your credentials:
    - `TENANT_ID`
    - `CLIENT_ID`
    - `CLIENT_SECRET`
    - `EMAIL`

2.  **Dockerized Execution**:
    To run this console app using Docker:
    ```bash
    docker compose up --build email-reader-console
    ```

## Development
To run locally (requires Python 3.11+):
```bash
pip install -r requirements.txt
python fetch_email.py
```

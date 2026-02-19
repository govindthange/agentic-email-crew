from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import logging
import msal
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Email Reader Service")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development; refine for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TENANT_ID = os.getenv("TENANT_ID")
EMAIL = os.getenv("EMAIL")

# Setup daily logging
today_str = datetime.now().strftime("%Y%m%d")
log_dir = "./logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
log_file = os.path.join(log_dir, f"service-{today_str}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
DATA_DIR = "./data"

def get_access_token():
    """Get OAuth2 token using client credentials (app-only auth)."""
    authority = f"https://login.microsoftonline.com/{TENANT_ID}"
    app_msal = msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=authority,
        client_credential=CLIENT_SECRET
    )
    result = app_msal.acquire_token_for_client(
        scopes=["https://graph.microsoft.com/.default"]
    )
    if "access_token" not in result:
        raise Exception(f"Failed to get token: {result.get('error_description')}")
    return result["access_token"]

def archive_email(email_data):
    """Appends email metadata to a daily JSON archive file."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    today = datetime.now().strftime("%Y%m%d")
    archive_file = os.path.join(DATA_DIR, f"archive-{today}.json")

    archive_data = []
    if os.path.exists(archive_file):
        try:
            with open(archive_file, "r") as f:
                archive_data = json.load(f)
                if not isinstance(archive_data, list):
                    archive_data = []
        except (json.JSONDecodeError, IOError):
            logging.warning(f"Failed to read {archive_file}, starting fresh.")
            archive_data = []

    if any(item.get("messageId") == email_data.get("messageId") for item in archive_data):
        logging.info(f"Email with messageId {email_data.get('messageId')} already exists in archive. Skipping.")
        return False

    archive_data.append(email_data)

    with open(archive_file, "w") as f:
        json.dump(archive_data, f, indent=4)
    
    logging.info(f"Email archived to {archive_file}")
    return True

@app.get("/api/email/fetch/last")
def fetch_last_email():
    try:
        logging.info("Acquiring OAuth token...")
        token = get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        logging.info(f"Fetching last email for {EMAIL}...")
        url = (
            f"{GRAPH_BASE}/users/{EMAIL}/mailFolders/inbox/messages"
            f"?$top=1&$orderby=receivedDateTime desc"
            f"&$select=from,toRecipients,ccRecipients,subject,"
            f"receivedDateTime,categories,internetMessageId,importance,body"
        )
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        messages = response.json().get("value", [])
        if not messages:
            return {"status": "success", "message": "No emails found in Inbox."}

        msg = messages[0]
        body_content = msg.get("body", {}).get("content", "")

        email_data = {
            "from": msg.get("from", {}).get("emailAddress", {}).get("address"),
            "to": [r["emailAddress"]["address"] for r in msg.get("toRecipients", [])],
            "cc": [r["emailAddress"]["address"] for r in msg.get("ccRecipients", [])],
            "subject": msg.get("subject"),
            "receivedOn": msg.get("receivedDateTime"),
            "category": msg.get("categories") or "N/A",
            "messageId": msg.get("internetMessageId"),
            "priority": msg.get("importance"),
            "contentType": "HTML" if "<html>" in body_content.lower() else "Text",
            "body": body_content
        }

        archived = archive_email(email_data)
        return {
            "status": "success",
            "archived": archived,
            "email": email_data
        }

    except Exception as e:
        logging.error(f"Error fetching email: {e}")
        raise HTTPException(status_code=500, detail=str(e))

from typing import Optional

@app.get("/api/emails")
def fetch_emails_by_range(start_date: Optional[str] = None, end_date: Optional[str] = None):
    try:
        logging.info(f"Acquiring OAuth token for fetch emails range ({start_date} to {end_date})...")
        token = get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        # Default start_date to today if not provided
        if not start_date:
            start_date = datetime.now().strftime("%Y-%m-%d")
        
        filter_query = f"receivedDateTime ge {start_date}T00:00:00Z"
        
        if end_date:
            filter_query += f" and receivedDateTime le {end_date}T23:59:59Z"
        
        url = (
            f"{GRAPH_BASE}/users/{EMAIL}/mailFolders/inbox/messages"
            f"?$filter={filter_query}"
            f"&$select=from,toRecipients,ccRecipients,subject,"
            f"receivedDateTime,categories,internetMessageId,importance,body"
            f"&$orderby=receivedDateTime desc"
        )

        total_fetched = 0
        newly_archived = 0

        while url:
            logging.info(f"Fetching page of emails from: {url}")
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            messages = data.get("value", [])
            total_fetched += len(messages)

            for msg in messages:
                body_content = msg.get("body", {}).get("content", "")
                email_data = {
                    "from": msg.get("from", {}).get("emailAddress", {}).get("address"),
                    "to": [r["emailAddress"]["address"] for r in msg.get("toRecipients", [])],
                    "cc": [r["emailAddress"]["address"] for r in msg.get("ccRecipients", [])],
                    "subject": msg.get("subject"),
                    "receivedOn": msg.get("receivedDateTime"),
                    "category": msg.get("categories") or "N/A",
                    "messageId": msg.get("internetMessageId"),
                    "priority": msg.get("importance"),
                    "contentType": "HTML" if "<html>" in body_content.lower() else "Text",
                    "body": body_content
                }
                
                if archive_email(email_data):
                    newly_archived += 1

            url = data.get("@odata.nextLink")

        return {
            "status": "success",
            "total_fetched": total_fetched,
            "newly_archived": newly_archived,
            "message": f"Processed {total_fetched} emails, {newly_archived} were new."
        }

    except Exception as e:
        logging.error(f"Error fetching all emails: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/email/read-count")
def read_count():
    return {"status": "Work In Progress"}

@app.get("/api/email/unread-count")
def unread_count():
    return {"status": "Work In Progress"}

@app.get("/api/email/archive-count")
def archive_count():
    try:
        total_count = 0
        if os.path.exists(DATA_DIR):
            for filename in os.listdir(DATA_DIR):
                if filename.startswith("archive-") and filename.endswith(".json"):
                    with open(os.path.join(DATA_DIR, filename), "r") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            total_count += len(data)
        return {"status": "success", "count": total_count}
    except Exception as e:
        logging.error(f"Error counting archive: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

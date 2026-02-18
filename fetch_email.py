import os
import json
import logging
import msal
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TENANT_ID = os.getenv("TENANT_ID")
EMAIL = os.getenv("EMAIL")  # The mailbox to read from

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

def get_access_token():
    """Get OAuth2 token using client credentials (app-only auth)."""
    authority = f"https://login.microsoftonline.com/{TENANT_ID}"
    app = msal.ConfidentialClientApplication(
        CLIENT_ID,
        authority=authority,
        client_credential=CLIENT_SECRET
    )
    result = app.acquire_token_for_client(
        scopes=["https://graph.microsoft.com/.default"]
    )
    if "access_token" not in result:
        raise Exception(f"Failed to get token: {result.get('error_description')}")
    return result["access_token"]

def fetch_last_email():
    try:
        logging.info("Acquiring OAuth token...")
        token = get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        logging.info(f"Fetching last email for {EMAIL}...")
        # Use /users/{email}/messages for app-only (client credentials) flow
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
            logging.info("No emails found in Inbox.")
            return

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
            "contentType": "HTML" if "<html>" in body_content.lower() else "Text"
        }

        logging.info("Successfully fetched last email.")
        logging.info("JSON metadata = " + json.dumps(email_data, indent=4))

    except requests.HTTPError as e:
        logging.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
    except Exception as e:
        logging.error(f"An error occurred: {e}")

if __name__ == "__main__":
    fetch_last_email()
# Email Reader Service

A FastAPI-based microservice that interacts with Microsoft Graph API to fetch and archive emails.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/email/fetch/last` | GET | Fetches the latest email and saves it to the local archive. |
| `/api/email/archive-count` | GET | Returns the total count of emails archived. |
| `/api/email/fetch/all` | GET | (Work In Progress) |
| `/api/email/read-count` | GET | (Work In Progress) |
| `/api/email/unread-count` | GET | (Work In Progress) |

## Setup

1.  **Environment Variables**: Ensure the `.env` file is configured with:
    - `TENANT_ID`
    - `CLIENT_ID`
    - `CLIENT_SECRET`
    - `EMAIL`

2.  **Run with Docker Compose**:
    From the project root:
    ```bash
    docker compose up --build -d email-reader-service
    ```

## Testing

You can test the endpoints using `curl`:

```bash
# Fetch the latest email
curl http://localhost:8000/api/email/fetch/last

# Check archive count
curl http://localhost:8000/api/email/archive-count
```

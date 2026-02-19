# The Email Crew

This workspace follows a microservices-style architecture for email automation and processing.

## Project Structure

- **[email-reader-service/](./email-reader-service/README.md)**: A FastAPI microservice for fetching and archiving emails via REST API.
- **[email-reader-console/](./email-reader-console/README.md)**: The original console-based email fetcher script.

## Getting Started

1.  **Environment Setup**: Each service may require its own `.env` file for credentials. Refer to the specific service folders for details.
2.  **Orchestration**: The entire suite can be managed using Docker Compose from this root directory.

```bash
# Start all services
docker compose up --build -d

# Start a specific service
docker compose up --build -d email-reader-service
```

## Documentation
Please navigate to the respective folders to read detailed instructions on how to use and test each microservice/component.

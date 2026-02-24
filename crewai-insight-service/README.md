# CrewAI Insight Service

This service provides automated email intelligence using multi-agent workflows.

## Features
- **File Watcher**: Automatically processes new email archives in `./data/archives`.
- **Cron Job**: Checks for unprocessed archives every 4 hours.
- **On-Demand API**: Trigger processing via `POST /process?date=YYYYMMDD`.

## Testing Instructions

### 1. Prerequisite: Ollama
Ensure Ollama is running and accessible. The agents require `mistral-nemo` and `qwen2.5:32b`.
Download them using:
```bash
ollama pull mistral-nemo
ollama pull qwen2.5:32b
ollama pull nomic-embed-text
```

### 2. Start the Service
Run the following command from the root directory:
```bash
docker-compose up -d crewai-insight-service
```

### 3. Manual Trigger
You can trigger processing via `curl` or simply by **opening the URL in your browser**:
- **Browser/GET**: `http://localhost:8001/process?date=20260223`
- **CURL/POST**:
```bash
curl -X POST "http://localhost:8001/process?date=20260223"
```

### 4. Direct File Trigger
Drop any `archive-YYYYMMDD.json` file into `email-reader-service/data/`. The service will detect it and start processing.

### 5. Check Outputs
Processed reports will be available in the root `./data` directory:
- `report-variation1-YYYYMMDD.md`
- `report-variation2-YYYYMMDD.md`
- `mindmap-variation1-YYYYMMDD.html`
- `mindmap-variation2-YYYYMMDD.html`

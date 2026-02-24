import logging
import os
import re
from datetime import datetime
from contextlib import asynccontextmanager

# Setup daily logging with absolute paths
today_str = datetime.now().strftime("%Y%m%d")
LOG_DIR = "/app/logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)
LOG_FILE = os.path.join(LOG_DIR, f"service-{today_str}.log")

import sys

# Unified logging configuration
handler = logging.FileHandler(LOG_FILE)
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
console_handler = logging.StreamHandler(sys.__stdout__) # Use original stdout for console
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Root logger setup
logging.root.setLevel(logging.INFO)
logging.root.addHandler(handler)
logging.root.addHandler(console_handler)

# Capture logs from other libraries
for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access", "litellm", "crewai"]:
    l = logging.getLogger(logger_name)
    l.handlers = [handler, console_handler]
    l.propagate = False

logger = logging.getLogger(__name__)

# Redirect stdout and stderr to logging
class StreamToLogger:
    def __init__(self, logger, level, original_stream):
        self.logger = logger
        self.level = level
        self.original_stream = original_stream
        self.ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    def write(self, buf):
        # Remove ANSI codes and log cleaned lines
        clean_buf = self.ansi_escape.sub('', buf)
        for line in clean_buf.splitlines():
            strip_line = line.strip()
            if not strip_line: continue
            
            # Heuristic: LiteLLM often prints INFO to stderr. Detect and re-level.
            actual_level = self.level
            if self.level == logging.ERROR:
                upper_line = strip_line.upper()
                info_keywords = ["INFO", "SUCCESS", "COMPLETED", "DEBUG", "COMPLETION", "OLLAMA", "LITELLM", "MODEL"]
                if any(kw in upper_line for kw in info_keywords):
                    actual_level = logging.INFO
            
            self.logger.log(actual_level, strip_line)
        self.original_stream.write(buf)

    def flush(self):
        self.original_stream.flush()

    def isatty(self):
        return self.original_stream.isatty()

    def fileno(self):
        return self.original_stream.fileno()

sys.stdout = StreamToLogger(logging.getLogger('STDOUT'), logging.INFO, sys.__stdout__)
sys.stderr = StreamToLogger(logging.getLogger('STDERR'), logging.ERROR, sys.__stderr__)

from fastapi import FastAPI, BackgroundTasks
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from apscheduler.schedulers.background import BackgroundScheduler
from crew import EmailInsightCrew

app = FastAPI(title="CrewAI Insight Service", lifespan=None) # Will set lifespan below
crew_manager = None

DATA_DIR = os.getenv("DATA_DIR", "/app/data")
ARCHIVE_DIR = os.path.join(DATA_DIR, "archives")

class ArchiveHandler(FileSystemEventHandler):
    def __init__(self, manager):
        self.manager = manager
        super().__init__()

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".json"):
            logger.info(f"New archive detected: {event.src_path}")
            if self.manager:
                self.manager.run(event.src_path)
            else:
                logger.error("Crew manager not initialized!")

def start_file_watcher(manager):
    if not os.path.exists(ARCHIVE_DIR):
        os.makedirs(ARCHIVE_DIR)
    
    event_handler = ArchiveHandler(manager)
    observer = Observer()
    observer.schedule(event_handler, ARCHIVE_DIR, recursive=False)
    observer.start()
    logger.info(f"File watcher started on {ARCHIVE_DIR}")
    return observer

def run_cron_job():
    logger.info("Running scheduled cron job...")
    # Logic to find unprocessed archives
    pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    global crew_manager
    crew_manager = EmailInsightCrew()
    
    observer = start_file_watcher(crew_manager)
    
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_cron_job, 'interval', hours=4)
    scheduler.start()
    logger.info("Cron scheduler started.")
    
    yield
    
    # Shutdown logic
    observer.stop()
    observer.join()
    scheduler.shutdown()
    logger.info("Service shutting down, observer and scheduler stopped.")

app = FastAPI(title="CrewAI Insight Service", lifespan=lifespan)

@app.api_route("/process", methods=["GET", "POST"])
async def process_on_demand(date: str, background_tasks: BackgroundTasks):
    archive_file = os.path.join(ARCHIVE_DIR, f"archive-{date}.json")
    if not os.path.exists(archive_file):
        return {"status": "error", "message": f"Archive not found for {date}"}
    
    try:
        background_tasks.add_task(crew_manager.run, archive_file)
    except Exception as e:
        logger.error(f"Failed to start background task for {date}: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}
        
    return {"status": "success", "message": f"Processing started for {date}"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, log_config=None)

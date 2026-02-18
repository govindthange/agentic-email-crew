FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY fetch_email.py .

# Create necessary files/directories
RUN touch app.log && mkdir -p data

# Run the script
CMD ["python", "fetch_email.py"]

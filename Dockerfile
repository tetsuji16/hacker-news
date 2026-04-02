FROM python:3.11-slim

# Install system dependencies (ffmpeg is required for pydub)
RUN apt-get update && apt-get install -y ffmpeg git build-essential python3-dev libxml2-dev libxslt-dev && rm -rf /var/lib/apt/lists/*

# Configure git to avoid ownership issues in mounted volumes
RUN git config --global --add safe.directory /app

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app ./app
COPY .env .

# Create output directory
RUN mkdir output

# Run the application
# Use -u for unbuffered output to see logs in Docker
CMD ["python", "-u", "-m", "app.main"]

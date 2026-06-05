FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (for building some scientific packages if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose FastAPI port
EXPOSE 8002

# Run the Uvicorn server
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8002"]

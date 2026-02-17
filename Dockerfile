# Use Python 3.11 slim image as base
# Specify platform to avoid exec format errors
FROM --platform=linux/amd64 python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Install system dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/

# Create necessary directories
RUN mkdir -p src/static/img

# Expose port 5000
EXPOSE 5000

# Run the Flask application
CMD ["python", "src/app.py"]


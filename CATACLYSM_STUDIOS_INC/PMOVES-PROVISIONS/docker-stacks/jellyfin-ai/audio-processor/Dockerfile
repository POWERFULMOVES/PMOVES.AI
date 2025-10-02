

FROM python:3.11-slim

WORKDIR /app


FROM python:3.11-slim

WORKDIR /app


# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    libsndfile1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*


# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/logs /app/output /app/temp

# Set permissions
RUN chmod +x /app/entrypoint.sh

EXPOSE 8001

CMD ["./entrypoint.sh"]


# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/logs /app/output /app/temp

# Set permissions
RUN chmod +x /app/entrypoint.sh

EXPOSE 8001

CMD ["./entrypoint.sh"]


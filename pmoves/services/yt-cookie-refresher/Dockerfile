FROM mcr.microsoft.com/playwright/python:v1.49.1-noble

WORKDIR /app

# Install Python deps first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium browser for Playwright
RUN playwright install chromium

# Copy service code
COPY *.py ./

# Non-root user (Playwright image provides pwuser)
USER pwuser

EXPOSE 8115

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=15s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8115/healthz', timeout=5)"

CMD ["python", "main.py"]

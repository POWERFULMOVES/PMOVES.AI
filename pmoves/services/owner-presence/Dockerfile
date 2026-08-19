FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8091
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8091"]

# Non-root runtime (house pattern; restores #2285 intent without truncating)
RUN useradd --create-home --shell /bin/bash pmoves 2>/dev/null || true
USER pmoves

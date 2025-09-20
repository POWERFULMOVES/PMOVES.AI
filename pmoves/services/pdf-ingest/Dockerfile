FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
RUN pip install --no-cache-dir --upgrade pip
COPY services/pdf-ingest/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY libs /app/libs
COPY services/common /app/services/common
COPY contracts /app/contracts
COPY services/pdf-ingest/ /app/
ENV PMOVES_CONTRACTS_DIR=/app/contracts
EXPOSE 8092
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8092"]

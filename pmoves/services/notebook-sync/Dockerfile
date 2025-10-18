FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir --upgrade pip
COPY services/notebook-sync/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY services/notebook-sync/ ./
EXPOSE 8095
CMD ["uvicorn","sync:app","--host","0.0.0.0","--port","8095"]

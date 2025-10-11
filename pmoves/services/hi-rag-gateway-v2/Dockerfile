FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app:/app/libs
RUN pip install --no-cache-dir --upgrade pip
# With build context at repo root
COPY libs /app/libs
COPY services/common /app/services/common
COPY services/hi-rag-gateway-v2/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY services/hi-rag-gateway-v2/ ./
# Include local scripts for seeding explicitly
COPY services/hi-rag-gateway-v2/scripts /app/scripts
COPY tools/chit_security.py /app/tools/chit_security.py
EXPOSE 8086
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8086"]

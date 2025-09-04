FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir --upgrade pip
COPY ../../libs /app/libs
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Include local scripts for seeding
COPY scripts /app/scripts
EXPOSE 8086
CMD ["uvicorn","app:app","--host","0.0.0.0","--port","8086"]

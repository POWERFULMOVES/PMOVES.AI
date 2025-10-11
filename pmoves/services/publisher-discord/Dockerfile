FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir --upgrade pip
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY services /app/services
EXPOSE 8092
CMD ["uvicorn","services.publisher-discord.main:app","--host","0.0.0.0","--port","8092"]


FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir nats-py>=2.7
COPY main.py .
RUN useradd -r -s /bin/false pmoves
USER pmoves
CMD ["python", "main.py"]

FROM python:3.10-slim
WORKDIR /app
RUN pip install --no-cache-dir nats-py==2.7.2 requests==2.32.3 PyYAML==6.0.2
COPY services/mesh-agent /app/
CMD ["python","main.py"]


FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
RUN useradd -r -s /bin/false pmoves
USER pmoves
CMD ["python", "main.py"]

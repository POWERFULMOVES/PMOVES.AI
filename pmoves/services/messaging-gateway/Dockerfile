FROM python:3.11-slim

WORKDIR /app

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash pmoves

COPY requirements.txt requirements.lock .
RUN pip install --no-cache-dir --constraint requirements.lock -r requirements.txt

COPY . .

# Change ownership to non-root user
RUN chown -R pmoves:pmoves /app

# Switch to non-root user
USER pmoves

ENV PORT=8101
EXPOSE 8101

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8101"]

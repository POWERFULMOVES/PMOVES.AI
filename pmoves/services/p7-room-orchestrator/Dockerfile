FROM python:3.11-slim

WORKDIR /app
COPY services/p7-room-orchestrator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/p7-room-orchestrator/app.py .
COPY config/rooms /app/pmoves/config/rooms
COPY config/signing_identity_cards.yaml /app/pmoves/config/signing_identity_cards.yaml
COPY contracts/schemas/identity/signing-card.v1.schema.json /app/pmoves/contracts/schemas/identity/signing-card.v1.schema.json

EXPOSE 8122
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8122"]

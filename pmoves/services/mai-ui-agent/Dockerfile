FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

COPY services/mai-ui-agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Shared secret helper (services/common/env.py::get_secret) — without this COPY
# the import below fails in-container; MAI_UI_API_KEY_FILE would be unresolvable.
COPY services/common /app/services/common
COPY services/mai-ui-agent/app.py .

EXPOSE 8220

CMD ["python", "app.py"]

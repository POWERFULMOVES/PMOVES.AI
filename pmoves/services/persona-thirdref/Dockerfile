FROM python:3.12-slim
WORKDIR /app
COPY services/persona-thirdref/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Root build context: the service ships WITH its contract schema so
# validation works inside the image without the repo tree.
COPY services/persona-thirdref/ ./services/persona-thirdref/
COPY contracts/schemas/persona/ /app/contracts/schemas/persona/
WORKDIR /app/services/persona-thirdref
ENV PYTHONUNBUFFERED=1
EXPOSE 8099
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8099"]

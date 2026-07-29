USER pmoves
RUN useradd --create-home --shell /bin/bash pmoves 2>/dev/null || true

CMD ["uvicorn", "mesh_exposure.app:app", "--host", "0.0.0.0", "--port", "8132"]

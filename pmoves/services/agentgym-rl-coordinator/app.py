import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
import nats
from nats.errors import ConnectionClosedError, TimeoutError, NoServersError

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agentgym-coordinator")

# Configuration
NATS_URL = os.getenv("NATS_URL", "nats://nats:4222")
HF_TOKEN = os.getenv("HF_TOKEN")
PORT = int(os.getenv("PORT", 8114))

# Global NATS Client
nc = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global nc
    try:
        logger.info(f"Connecting to NATS at {NATS_URL}...")
        nc = await nats.connect(NATS_URL)
        logger.info("Connected to NATS.")
        
        # Subscribe to Geometry Bus events (Simulation Actions)
        async def message_handler(msg):
            subject = msg.subject
            data = msg.data.decode()
            logger.info(f"Received geometry event on {subject}: {len(data)} bytes")
            # TODO: Accumulate trajectory for dataset creation
            
        await nc.subscribe("geometry.event.v1", cb=message_handler)
        
    except Exception as e:
        logger.error(f"Failed to connect to NATS: {e}")

    yield
    
    # Shutdown
    if nc:
        await nc.close()

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health_check():
    nats_status = "connected" if nc and nc.is_connected else "disconnected"
    hf_status = "configured" if HF_TOKEN else "missing"
    return {"status": "ok", "nats": nats_status, "huggingface": hf_status}

@app.post("/agentgym/train/start")
async def start_training(run_id: str):
    logger.info(f"Triggering training run: {run_id}")
    # TODO: Implement PPO training loop triggering
    return {"status": "training_started", "run_id": run_id}

@app.post("/agentgym/dataset/publish")
async def publish_dataset(dataset_name: str):
    if not HF_TOKEN:
        raise HTTPException(status_code=500, detail="HF_TOKEN not configured")
    
    logger.info(f"Publishing dataset {dataset_name} to Hugging Face...")
    # TODO: Implement dataset push logic via huggingface_hub
    return {"status": "publishing_started", "dataset": dataset_name}

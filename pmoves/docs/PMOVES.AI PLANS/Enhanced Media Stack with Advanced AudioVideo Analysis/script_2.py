import os

# Create directory structure first
os.makedirs('audio-ai-service', exist_ok=True)

# Audio AI Service main.py
audio_ai_main = '''
# Enhanced Audio AI Service with Multiple Models
import asyncio
import os
import logging
from pathlib import Path
import json
import tempfile
from typing import Dict, List, Optional
import uuid
from datetime import datetime

import torch
import torchaudio
import librosa
import numpy as np
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn
from pydub import AudioSegment
from pydantic import BaseModel

# AI Model imports - with error handling for missing packages
try:
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    print("Warning: transformers not available")

try:
    import whisperx
    WHISPERX_AVAILABLE = True
except ImportError:
    WHISPERX_AVAILABLE = False
    print("Warning: whisperx not available")

try:
    from pyannote.audio import Pipeline as PyannoteePipeline
    PYANNOTE_AVAILABLE = True
except ImportError:
    PYANNOTE_AVAILABLE = False
    print("Warning: pyannote.audio not available")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Enhanced Audio AI Service", version="2.0.0")

class AudioAnalysisRequest(BaseModel):
    file_path: str
    analysis_type: str = "full"
    language: str = "auto"
    output_format: str = "json"

class EnhancedAudioProcessor:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        self.models = {}
        self.load_models()
        
    def load_models(self):
        """Load available AI models for audio processing"""
        logger.info(f"Loading models on device: {self.device}")
        
        # Load Whisper if available
        if TRANSFORMERS_AVAILABLE:
            try:
                model_id = "openai/whisper-large-v3"
                model = AutoModelForSpeechSeq2Seq.from_pretrained(
                    model_id, torch_dtype=self.torch_dtype, low_cpu_mem_usage=True
                )
                model.to(self.device)
                processor = AutoProcessor.from_pretrained(model_id)
                
                self.models['whisper'] = pipeline(
                    "automatic-speech-recognition",
                    model=model,
                    tokenizer=processor.tokenizer,
                    feature_extractor=processor.feature_extractor,
                    torch_dtype=self.torch_dtype,
                    device=self.device
                )
                logger.info("✓ Whisper Large v3 loaded")
            except Exception as e:
                logger.error(f"Failed to load Whisper: {e}")
        
        # Load emotion recognition
        if TRANSFORMERS_AVAILABLE:
            try:
                self.models['emotion'] = pipeline(
                    "audio-classification",
                    model="superb/hubert-large-superb-er",
                    device=0 if self.device == "cuda" else -1
                )
                logger.info("✓ Emotion recognition loaded")
            except Exception as e:
                logger.error(f"Failed to load emotion model: {e}")
        
        logger.info(f"Loaded {len(self.models)} models successfully")
    
    def extract_audio_features(self, audio_path: str) -> Dict:
        """Extract technical audio features using librosa"""
        try:
            y, sr = librosa.load(audio_path, sr=16000)
            
            features = {
                'duration': float(len(y) / sr),
                'sample_rate': int(sr),
                'rms_energy': float(librosa.feature.rms(y=y).mean()),
                'spectral_centroid': float(librosa.feature.spectral_centroid(y=y, sr=sr).mean()),
                'spectral_bandwidth': float(librosa.feature.spectral_bandwidth(y=y, sr=sr).mean()),
                'spectral_rolloff': float(librosa.feature.spectral_rolloff(y=y, sr=sr).mean()),
                'zero_crossing_rate': float(librosa.feature.zero_crossing_rate(y).mean()),
                'chroma_stft': librosa.feature.chroma_stft(y=y, sr=sr).mean(axis=1).tolist(),
                'mfccs': librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13).mean(axis=1).tolist()
            }
            
            # Extract tempo and beats
            tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
            features['tempo'] = float(tempo)
            features['beat_count'] = len(beats)
            
            return features
        except Exception as e:
            logger.error(f"Error extracting audio features: {e}")
            return {}
    
    async def transcribe_audio(self, audio_path: str, language: str = "auto") -> Dict:
        """Transcribe audio using available models"""
        if 'whisper' not in self.models:
            return {'error': 'No transcription model available'}
        
        try:
            result = self.models['whisper'](
                audio_path,
                return_timestamps=True,
                generate_kwargs={
                    "language": None if language == "auto" else language,
                    "task": "transcribe"
                }
            )
            
            return {
                'text': result['text'],
                'chunks': result.get('chunks', []),
                'model': 'whisper-large-v3'
            }
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return {'error': str(e)}
    
    async def analyze_emotions(self, audio_path: str) -> Dict:
        """Analyze emotional content"""
        if 'emotion' not in self.models:
            return {'error': 'No emotion model available'}
        
        try:
            result = self.models['emotion'](audio_path)
            return {
                'emotions': result,
                'dominant_emotion': max(result, key=lambda x: x['score']),
                'model': 'hubert-emotion'
            }
        except Exception as e:
            logger.error(f"Emotion analysis error: {e}")
            return {'error': str(e)}
    
    async def full_analysis(self, audio_path: str, language: str = "auto") -> Dict:
        """Perform comprehensive audio analysis"""
        start_time = datetime.now()
        
        results = {
            'task_id': str(uuid.uuid4()),
            'file_path': audio_path,
            'timestamp': start_time.isoformat(),
            'status': 'processing'
        }
        
        # Extract features
        logger.info("Extracting audio features...")
        results['features'] = self.extract_audio_features(audio_path)
        
        # Transcription
        logger.info("Transcribing audio...")
        results['transcription'] = await self.transcribe_audio(audio_path, language)
        
        # Emotion analysis
        logger.info("Analyzing emotions...")
        results['emotions'] = await self.analyze_emotions(audio_path)
        
        # Processing time
        end_time = datetime.now()
        results['processing_time'] = (end_time - start_time).total_seconds()
        results['status'] = 'completed'
        
        logger.info(f"Analysis completed in {results['processing_time']:.2f} seconds")
        return results

# Global processor instance
processor = EnhancedAudioProcessor()

@app.post("/analyze")
async def analyze_audio(request: AudioAnalysisRequest):
    """Analyze audio file"""
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    try:
        if request.analysis_type == "full":
            result = await processor.full_analysis(request.file_path, request.language)
        elif request.analysis_type == "transcription":
            result = await processor.transcribe_audio(request.file_path, request.language)
        elif request.analysis_type == "emotion":
            result = await processor.analyze_emotions(request.file_path)
        else:
            raise HTTPException(status_code=400, detail="Invalid analysis type")
        
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "models_loaded": list(processor.models.keys()),
        "device": processor.device
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, log_level="info")
'''

# Audio AI Service Dockerfile
audio_dockerfile = '''
FROM nvidia/cuda:12.1-devel-ubuntu22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    python3 \\
    python3-pip \\
    python3-dev \\
    ffmpeg \\
    libsndfile1 \\
    git \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python packages
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/uploads /app/cache /app/models

EXPOSE 8001

CMD ["python3", "main.py"]
'''

# Audio AI Service requirements
audio_requirements = '''
fastapi==0.104.1
uvicorn[standard]==0.24.0
torch>=2.0.0
torchaudio>=2.0.0
transformers>=4.35.0
librosa==0.10.1
pydub==0.25.1
numpy>=1.24.0
scipy>=1.10.0
soundfile>=0.12.0
python-multipart==0.0.6
pydantic>=2.0.0
whisper-openai
pyannote.audio
speechbrain
datasets
accelerate
'''

# Save files
with open('audio-ai-service/main.py', 'w') as f:
    f.write(audio_ai_main)

with open('audio-ai-service/Dockerfile', 'w') as f:
    f.write(audio_dockerfile)

with open('audio-ai-service/requirements.txt', 'w') as f:
    f.write(audio_requirements)

print("✓ Audio AI Service created with:")
print("- Whisper Large v3 for transcription")
print("- Emotion recognition model")
print("- Comprehensive audio feature extraction")
print("- FastAPI web service")
print("- Docker configuration with GPU support")
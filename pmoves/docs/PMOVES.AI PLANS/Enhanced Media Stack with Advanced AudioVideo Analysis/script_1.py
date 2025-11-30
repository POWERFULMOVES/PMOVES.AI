# Create the enhanced audio AI service with multiple models

audio_ai_service_code = '''
# Enhanced Audio AI Service with Multiple Models
import asyncio
import os
import logging
from pathlib import Path
import json
import tempfile
from typing import Dict, List, Optional, Tuple
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

# AI Model imports
from transformers import (
    AutoModelForSpeechSeq2Seq, 
    AutoProcessor, 
    pipeline,
    Qwen2AudioForConditionalGeneration
)
import whisperx
from pyannote.audio import Pipeline
from speechbox import ASRDiarizationPipeline

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Enhanced Audio AI Service", version="2.0.0")

class AudioAnalysisRequest(BaseModel):
    file_path: str
    analysis_type: str = "full"  # full, transcription, diarization, emotion
    language: str = "auto"
    output_format: str = "json"

class AudioAnalysisResult(BaseModel):
    task_id: str
    status: str
    transcription: Optional[str] = None
    speakers: Optional[List[Dict]] = None
    emotions: Optional[List[Dict]] = None
    features: Optional[Dict] = None
    metadata: Optional[Dict] = None
    processing_time: Optional[float] = None

class EnhancedAudioProcessor:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        
        # Initialize models
        self.models = {}
        self.load_models()
        
    def load_models(self):
        """Load all AI models for audio processing"""
        logger.info(f"Loading models on device: {self.device}")
        
        # 1. Whisper Large v3 Turbo for transcription
        try:
            model_id = "openai/whisper-large-v3"
            model = AutoModelForSpeechSeq2Seq.from_pretrained(
                model_id, 
                torch_dtype=self.torch_dtype, 
                low_cpu_mem_usage=True, 
                use_safetensors=True
            )
            model.to(self.device)
            processor = AutoProcessor.from_pretrained(model_id)
            
            self.models['whisper'] = pipeline(
                "automatic-speech-recognition",
                model=model,
                tokenizer=processor.tokenizer,
                feature_extractor=processor.feature_extractor,
                torch_dtype=self.torch_dtype,
                device=self.device,
                chunk_length_s=30,
                batch_size=8
            )
            logger.info("✓ Whisper Large v3 loaded")
        except Exception as e:
            logger.error(f"Failed to load Whisper: {e}")
        
        # 2. WhisperX for enhanced transcription with diarization
        try:
            self.models['whisperx'] = whisperx.load_model(
                "large-v3", 
                self.device, 
                compute_type="float16" if self.device == "cuda" else "float32"
            )
            
            # Load alignment model
            self.models['align_model'], self.models['align_metadata'] = whisperx.load_align_model(
                language_code="en", 
                device=self.device
            )
            
            # Load diarization pipeline
            self.models['diarize_model'] = whisperx.DiarizationPipeline(
                use_auth_token=os.getenv("HF_TOKEN"), 
                device=self.device
            )
            logger.info("✓ WhisperX with diarization loaded")
        except Exception as e:
            logger.error(f"Failed to load WhisperX: {e}")
        
        # 3. Pyannote for advanced speaker diarization
        try:
            self.models['pyannote'] = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=os.getenv("HF_TOKEN")
            ).to(torch.device(self.device))
            logger.info("✓ Pyannote diarization loaded")
        except Exception as e:
            logger.error(f"Failed to load Pyannote: {e}")
        
        # 4. Emotion recognition model
        try:
            self.models['emotion'] = pipeline(
                "audio-classification",
                model="superb/hubert-large-superb-er",
                device=0 if self.device == "cuda" else -1
            )
            logger.info("✓ Emotion recognition loaded")
        except Exception as e:
            logger.error(f"Failed to load emotion model: {e}")
        
        # 5. SeaLLMs Audio for advanced analysis
        try:
            self.models['seallms'] = Qwen2AudioForConditionalGeneration.from_pretrained(
                "SeaLLMs/SeaLLMs-Audio-7B", 
                device_map="auto",
                torch_dtype=self.torch_dtype
            )
            self.models['seallms_processor'] = AutoProcessor.from_pretrained(
                "SeaLLMs/SeaLLMs-Audio-7B"
            )
            logger.info("✓ SeaLLMs Audio loaded")
        except Exception as e:
            logger.error(f"Failed to load SeaLLMs: {e}")
    
    def extract_audio_features(self, audio_path: str) -> Dict:
        """Extract technical audio features using librosa"""
        try:
            y, sr = librosa.load(audio_path, sr=16000)
            
            # Extract comprehensive features
            features = {
                'duration': float(len(y) / sr),
                'sample_rate': int(sr),
                'rms_energy': float(librosa.feature.rms(y=y).mean()),
                'spectral_centroid': float(librosa.feature.spectral_centroid(y=y, sr=sr).mean()),
                'spectral_bandwidth': float(librosa.feature.spectral_bandwidth(y=y, sr=sr).mean()),
                'spectral_rolloff': float(librosa.feature.spectral_rolloff(y=y, sr=sr).mean()),
                'zero_crossing_rate': float(librosa.feature.zero_crossing_rate(y).mean()),
                'chroma_stft': librosa.feature.chroma_stft(y=y, sr=sr).mean(axis=1).tolist(),
                'mel_frequency_cepstral_coefficients': librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13).mean(axis=1).tolist()
            }
            
            # Extract tempo and beats
            tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
            features['tempo'] = float(tempo)
            features['beat_times'] = beats.tolist()
            
            return features
            
        except Exception as e:
            logger.error(f"Error extracting audio features: {e}")
            return {}
    
    async def transcribe_with_whisper(self, audio_path: str, language: str = "auto") -> Dict:
        """Transcribe audio using Whisper Large v3"""
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
            logger.error(f"Whisper transcription error: {e}")
            return {'error': str(e)}
    
    async def transcribe_with_whisperx(self, audio_path: str) -> Dict:
        """Enhanced transcription with WhisperX including diarization"""
        try:
            # Load audio
            audio = whisperx.load_audio(audio_path)
            
            # 1. Transcribe with WhisperX
            result = self.models['whisperx'].transcribe(audio, batch_size=16)
            
            # 2. Align whisper output
            result = whisperx.align(
                result['segments'], 
                self.models['align_model'], 
                self.models['align_metadata'], 
                audio, 
                self.device, 
                return_char_alignments=False
            )
            
            # 3. Assign speaker labels
            diarize_segments = self.models['diarize_model'](audio)
            result = whisperx.assign_word_speakers(diarize_segments, result)
            
            return {
                'segments': result['segments'],
                'word_segments': result.get('word_segments', []),
                'diarization': diarize_segments.itertracks(yield_label=True),
                'model': 'whisperx'
            }
        except Exception as e:
            logger.error(f"WhisperX error: {e}")
            return {'error': str(e)}
    
    async def analyze_speakers(self, audio_path: str) -> Dict:
        """Advanced speaker diarization using Pyannote"""
        try:
            # Apply pretrained pipeline
            diarization = self.models['pyannote'](audio_path)
            
            speakers = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                speakers.append({
                    'speaker': speaker,
                    'start': turn.start,
                    'end': turn.end,
                    'duration': turn.end - turn.start
                })
            
            # Get speaker statistics
            unique_speakers = list(set([s['speaker'] for s in speakers]))
            speaker_stats = {}
            
            for speaker in unique_speakers:
                speaker_segments = [s for s in speakers if s['speaker'] == speaker]
                total_duration = sum([s['duration'] for s in speaker_segments])
                speaker_stats[speaker] = {
                    'total_duration': total_duration,
                    'segment_count': len(speaker_segments),
                    'segments': speaker_segments
                }
            
            return {
                'speakers': speakers,
                'speaker_count': len(unique_speakers),
                'speaker_statistics': speaker_stats,
                'model': 'pyannote-3.1'
            }
        except Exception as e:
            logger.error(f"Speaker diarization error: {e}")
            return {'error': str(e)}
    
    async def analyze_emotions(self, audio_path: str) -> Dict:
        """Analyze emotional content in audio"""
        try:
            # Load and preprocess audio for emotion analysis
            audio, sr = librosa.load(audio_path, sr=16000)
            
            # Split audio into segments for emotion analysis
            segment_length = 30  # 30 seconds
            segments = []
            
            for i in range(0, len(audio), segment_length * sr):
                segment = audio[i:i + segment_length * sr]
                if len(segment) > sr:  # At least 1 second
                    segments.append(segment)
            
            emotions = []
            for i, segment in enumerate(segments):
                try:
                    # Save temporary segment
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                        torchaudio.save(tmp_file.name, torch.tensor(segment).unsqueeze(0), sr)
                        
                        result = self.models['emotion'](tmp_file.name)
                        emotions.append({
                            'segment': i,
                            'start_time': i * segment_length,
                            'end_time': min((i + 1) * segment_length, len(audio) / sr),
                            'emotions': result
                        })
                        
                        os.unlink(tmp_file.name)
                except Exception as e:
                    logger.error(f"Emotion analysis segment {i} error: {e}")
                    continue
            
            return {
                'emotions': emotions,
                'dominant_emotions': self._get_dominant_emotions(emotions),
                'model': 'hubert-large-emotion'
            }
        except Exception as e:
            logger.error(f"Emotion analysis error: {e}")
            return {'error': str(e)}
    
    def _get_dominant_emotions(self, emotions: List[Dict]) -> Dict:
        """Calculate dominant emotions across the entire audio"""
        emotion_scores = {}
        total_segments = len(emotions)
        
        if total_segments == 0:
            return {}
        
        for segment in emotions:
            for emotion_result in segment['emotions']:
                emotion = emotion_result['label']
                score = emotion_result['score']
                if emotion not in emotion_scores:
                    emotion_scores[emotion] = []
                emotion_scores[emotion].append(score)
        
        # Calculate average scores
        dominant_emotions = {}
        for emotion, scores in emotion_scores.items():
            dominant_emotions[emotion] = {
                'average_score': sum(scores) / len(scores),
                'max_score': max(scores),
                'appearances': len(scores),
                'frequency': len(scores) / total_segments
            }
        
        return dominant_emotions
    
    async def advanced_analysis_with_seallms(self, audio_path: str, prompt: str = None) -> Dict:
        """Advanced audio analysis using SeaLLMs Audio model"""
        try:
            if 'seallms' not in self.models:
                return {'error': 'SeaLLMs model not available'}
            
            # Load audio for SeaLLMs
            audio_data, sr = librosa.load(
                audio_path, 
                sr=self.models['seallms_processor'].feature_extractor.sampling_rate
            )
            
            # Prepare conversation
            if not prompt:
                prompt = "Analyze this audio content. Describe the genre, mood, instruments, vocals, topics discussed, and any notable characteristics in detail."
            
            conversation = [{
                "role": "user", 
                "content": [
                    {"type": "audio", "audio_url": audio_path},
                    {"type": "text", "text": prompt}
                ]
            }]
            
            # Process with SeaLLMs
            text = self.models['seallms_processor'].apply_chat_template(
                conversation, 
                add_generation_prompt=True, 
                tokenize=False
            )
            
            inputs = self.models['seallms_processor'](
                text=text, 
                audios=[audio_data], 
                return_tensors="pt", 
                padding=True,
                sampling_rate=16000
            )
            
            inputs = {k: v.to(self.device) for k, v in inputs.items() if v is not None}
            
            generate_ids = self.models['seallms'].generate(
                **inputs, 
                max_new_tokens=2048, 
                temperature=0.7, 
                do_sample=True
            )
            
            generate_ids = generate_ids[:, inputs["input_ids"].size(1):]
            response = self.models['seallms_processor'].batch_decode(
                generate_ids, 
                skip_special_tokens=True, 
                clean_up_tokenization_spaces=False
            )[0]
            
            return {
                'analysis': response,
                'prompt': prompt,
                'model': 'seallms-audio-7b'
            }
        except Exception as e:
            logger.error(f"SeaLLMs analysis error: {e}")
            return {'error': str(e)}
    
    async def full_analysis(self, audio_path: str, language: str = "auto") -> Dict:
        """Perform comprehensive audio analysis"""
        start_time = datetime.now()
        
        results = {
            'task_id': str(uuid.uuid4()),
            'file_path': audio_path,
            'timestamp': start_time.isoformat(),
            'analysis_results': {}
        }
        
        # 1. Extract basic audio features
        logger.info("Extracting audio features...")
        results['analysis_results']['features'] = self.extract_audio_features(audio_path)
        
        # 2. Transcription with Whisper
        logger.info("Transcribing with Whisper...")
        results['analysis_results']['transcription'] = await self.transcribe_with_whisper(audio_path, language)
        
        # 3. Enhanced transcription with WhisperX
        logger.info("Enhanced transcription with WhisperX...")
        results['analysis_results']['enhanced_transcription'] = await self.transcribe_with_whisperx(audio_path)
        
        # 4. Speaker diarization
        logger.info("Analyzing speakers...")
        results['analysis_results']['speakers'] = await self.analyze_speakers(audio_path)
        
        # 5. Emotion analysis
        logger.info("Analyzing emotions...")
        results['analysis_results']['emotions'] = await self.analyze_emotions(audio_path)
        
        # 6. Advanced analysis with SeaLLMs
        logger.info("Advanced analysis with SeaLLMs...")
        results['analysis_results']['advanced_analysis'] = await self.advanced_analysis_with_seallms(audio_path)
        
        # Calculate processing time
        end_time = datetime.now()
        results['processing_time'] = (end_time - start_time).total_seconds()
        results['status'] = 'completed'
        
        logger.info(f"Full analysis completed in {results['processing_time']:.2f} seconds")
        return results

# Global processor instance
processor = EnhancedAudioProcessor()

@app.post("/analyze", response_model=AudioAnalysisResult)
async def analyze_audio(
    background_tasks: BackgroundTasks,
    request: AudioAnalysisRequest
):
    """Analyze audio file with specified analysis type"""
    
    if not os.path.exists(request.file_path):
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    try:
        if request.analysis_type == "full":
            result = await processor.full_analysis(request.file_path, request.language)
        elif request.analysis_type == "transcription":
            result = await processor.transcribe_with_whisper(request.file_path, request.language)
        elif request.analysis_type == "diarization":
            result = await processor.analyze_speakers(request.file_path)
        elif request.analysis_type == "emotion":
            result = await processor.analyze_emotions(request.file_path)
        else:
            raise HTTPException(status_code=400, detail="Invalid analysis type")
        
        return AudioAnalysisResult(**result)
        
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-and-analyze")
async def upload_and_analyze(
    file: UploadFile = File(...),
    analysis_type: str = "full",
    language: str = "auto"
):
    """Upload audio file and analyze it"""
    
    # Save uploaded file
    upload_dir = Path("/app/uploads")
    upload_dir.mkdir(exist_ok=True)
    
    file_path = upload_dir / f"{uuid.uuid4()}_{file.filename}"
    
    try:
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Analyze the uploaded file
        request = AudioAnalysisRequest(
            file_path=str(file_path),
            analysis_type=analysis_type,
            language=language
        )
        
        if analysis_type == "full":
            result = await processor.full_analysis(str(file_path), language)
        elif analysis_type == "transcription":
            result = await processor.transcribe_with_whisper(str(file_path), language)
        elif analysis_type == "diarization":
            result = await processor.analyze_speakers(str(file_path))
        elif analysis_type == "emotion":
            result = await processor.analyze_emotions(str(file_path))
        else:
            raise HTTPException(status_code=400, detail="Invalid analysis type")
        
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.error(f"Upload and analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up uploaded file
        if file_path.exists():
            file_path.unlink()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "models_loaded": list(processor.models.keys()),
        "device": processor.device
    }

@app.get("/models")
async def list_models():
    """List available models and their status"""
    return {
        "models": {
            name: "loaded" if name in processor.models else "not_loaded"
            for name in [
                "whisper", "whisperx", "pyannote", "emotion", "seallms"
            ]
        },
        "device": processor.device,
        "gpu_available": torch.cuda.is_available()
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        log_level="info",
        reload=False
    )
'''

# Save the enhanced audio service
with open('audio-ai-service/main.py', 'w') as f:
    f.write(audio_ai_service_code)

print("✓ Enhanced Audio AI Service created with:")
print("- Whisper Large v3 Turbo")
print("- WhisperX with diarization")
print("- Pyannote speaker diarization")
print("- Emotion recognition")
print("- SeaLLMs Audio for advanced analysis")
print("- Comprehensive feature extraction")
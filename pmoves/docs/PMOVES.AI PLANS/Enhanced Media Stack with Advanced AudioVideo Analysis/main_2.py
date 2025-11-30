
# Entity Extraction Service with Google LangExtract
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import uuid
from datetime import datetime
import json
import textwrap

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# LangExtract imports with error handling
try:
    import langextract as lx
    LANGEXTRACT_AVAILABLE = True
except ImportError:
    LANGEXTRACT_AVAILABLE = False
    print("Warning: langextract not available")

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Entity Extraction Service", version="2.0.0")

class EntityExtractionRequest(BaseModel):
    text: str
    extraction_type: str = "general"  # general, media, music, financial, academic
    custom_prompt: Optional[str] = None
    custom_examples: Optional[List[Dict]] = None
    model_id: str = "gemini-2.0-flash-exp"

class EntityExtractionResult(BaseModel):
    task_id: str
    status: str
    extractions: List[Dict] = []
    metadata: Dict = {}
    processing_time: float = 0.0
    error: Optional[str] = None

class EntityExtractor:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("LANGEXTRACT_API_KEY")
        self.extraction_templates = self._load_templates()

        if not self.api_key:
            logger.warning("No Gemini API key found. Set GEMINI_API_KEY or LANGEXTRACT_API_KEY")

    def _load_templates(self) -> Dict[str, Dict]:
        """Load predefined extraction templates"""
        return {
            "general": {
                "prompt": textwrap.dedent("""
                    Extract entities including people, organizations, locations, dates, and key concepts.
                    Use exact text for extractions. Do not paraphrase or overlap entities.
                    Provide meaningful attributes for each entity to add context.
                """),
                "examples": [
                    lx.data.ExampleData(
                        text="Apple Inc. announced record quarterly revenue of $123.9 billion on January 27, 2024, led by CEO Tim Cook in Cupertino, California.",
                        extractions=[
                            lx.data.Extraction(
                                extraction_class="organization",
                                extraction_text="Apple Inc.",
                                attributes={"type": "technology company", "sector": "consumer electronics"}
                            ),
                            lx.data.Extraction(
                                extraction_class="person",
                                extraction_text="Tim Cook",
                                attributes={"role": "CEO", "organization": "Apple Inc."}
                            ),
                            lx.data.Extraction(
                                extraction_class="financial_metric",
                                extraction_text="$123.9 billion",
                                attributes={"type": "quarterly revenue", "period": "Q1 2024"}
                            ),
                            lx.data.Extraction(
                                extraction_class="location",
                                extraction_text="Cupertino, California",
                                attributes={"type": "headquarters", "country": "USA"}
                            ),
                            lx.data.Extraction(
                                extraction_class="date",
                                extraction_text="January 27, 2024",
                                attributes={"event": "earnings announcement"}
                            )
                        ]
                    )
                ] if LANGEXTRACT_AVAILABLE else []
            },

            "media": {
                "prompt": textwrap.dedent("""
                    Extract media-related entities including artists, songs, albums, genres, instruments, 
                    record labels, and production details. Focus on music and entertainment content.
                    Use exact text and provide detailed attributes for music analysis.
                """),
                "examples": [
                    lx.data.ExampleData(
                        text="The Beatles' album 'Abbey Road' was recorded at Abbey Road Studios in London, featuring George Martin as producer. The track 'Come Together' showcases John Lennon's bass-heavy composition.",
                        extractions=[
                            lx.data.Extraction(
                                extraction_class="artist",
                                extraction_text="The Beatles",
                                attributes={"type": "band", "genre": "rock", "era": "1960s"}
                            ),
                            lx.data.Extraction(
                                extraction_class="album",
                                extraction_text="Abbey Road",
                                attributes={"artist": "The Beatles", "studio": "Abbey Road Studios"}
                            ),
                            lx.data.Extraction(
                                extraction_class="song",
                                extraction_text="Come Together",
                                attributes={"album": "Abbey Road", "composer": "John Lennon", "characteristics": "bass-heavy"}
                            ),
                            lx.data.Extraction(
                                extraction_class="person",
                                extraction_text="George Martin",
                                attributes={"role": "producer", "associated_with": "The Beatles"}
                            ),
                            lx.data.Extraction(
                                extraction_class="location",
                                extraction_text="Abbey Road Studios",
                                attributes={"type": "recording studio", "city": "London"}
                            )
                        ]
                    )
                ] if LANGEXTRACT_AVAILABLE else []
            },

            "music_analysis": {
                "prompt": textwrap.dedent("""
                    Extract detailed music analysis entities including genres, moods, instruments, 
                    technical aspects, lyrical themes, and production techniques.
                    Focus on elements useful for music recommendation and content analysis.
                """),
                "examples": [
                    lx.data.ExampleData(
                        text="This energetic indie rock track features distorted electric guitars, driving drum patterns, and introspective lyrics about urban alienation. The production uses heavy compression and reverb, creating a wall-of-sound effect typical of shoegaze influences.",
                        extractions=[
                            lx.data.Extraction(
                                extraction_class="genre",
                                extraction_text="indie rock",
                                attributes={"primary": True, "energy_level": "energetic"}
                            ),
                            lx.data.Extraction(
                                extraction_class="instrument",
                                extraction_text="distorted electric guitars",
                                attributes={"role": "lead", "effect": "distortion", "prominence": "high"}
                            ),
                            lx.data.Extraction(
                                extraction_class="mood",
                                extraction_text="introspective",
                                attributes={"aspect": "lyrics", "theme": "urban alienation"}
                            ),
                            lx.data.Extraction(
                                extraction_class="production_technique",
                                extraction_text="wall-of-sound effect",
                                attributes={"influences": "shoegaze", "methods": ["heavy compression", "reverb"]}
                            )
                        ]
                    )
                ] if LANGEXTRACT_AVAILABLE else []
            },

            "youtube_content": {
                "prompt": textwrap.dedent("""
                    Extract entities relevant for YouTube content analysis including topics, 
                    content types, audience engagement elements, and optimization keywords.
                    Focus on elements useful for content creation and SEO.
                """),
                "examples": [
                    lx.data.ExampleData(
                        text="This tutorial video covers music production basics using FL Studio, targeting beginner producers. Includes beat making, mixing techniques, and plugin recommendations. Great for music production enthusiasts and aspiring beat makers.",
                        extractions=[
                            lx.data.Extraction(
                                extraction_class="content_type",
                                extraction_text="tutorial video",
                                attributes={"format": "educational", "difficulty": "beginner"}
                            ),
                            lx.data.Extraction(
                                extraction_class="topic",
                                extraction_text="music production basics",
                                attributes={"software": "FL Studio", "scope": "basics"}
                            ),
                            lx.data.Extraction(
                                extraction_class="audience",
                                extraction_text="beginner producers",
                                attributes={"experience_level": "beginner", "interest": "music production"}
                            ),
                            lx.data.Extraction(
                                extraction_class="technique",
                                extraction_text="mixing techniques",
                                attributes={"category": "audio engineering", "skill_level": "intermediate"}
                            )
                        ]
                    )
                ] if LANGEXTRACT_AVAILABLE else []
            }
        }

    async def extract_entities(self, request: EntityExtractionRequest) -> Dict:
        """Extract entities using LangExtract"""
        if not LANGEXTRACT_AVAILABLE:
            return {
                'error': 'LangExtract not available',
                'suggestion': 'Install langextract: pip install langextract'
            }

        if not self.api_key:
            return {
                'error': 'No Gemini API key configured',
                'suggestion': 'Set GEMINI_API_KEY environment variable'
            }

        start_time = datetime.now()
        task_id = str(uuid.uuid4())

        try:
            # Get extraction configuration
            if request.custom_prompt and request.custom_examples:
                prompt = request.custom_prompt
                examples = request.custom_examples
            else:
                template = self.extraction_templates.get(
                    request.extraction_type, 
                    self.extraction_templates["general"]
                )
                prompt = template["prompt"]
                examples = template["examples"]

            # Perform extraction
            result = lx.extract(
                text_or_documents=request.text,
                prompt_description=prompt,
                examples=examples,
                model_id=request.model_id,
                api_key=self.api_key,
                extraction_passes=2,  # Multiple passes for better recall
                max_workers=10,       # Parallel processing
                max_char_buffer=2000  # Reasonable context size
            )

            # Process results
            extractions = []
            for extraction in result.extractions:
                extractions.append({
                    'class': extraction.extraction_class,
                    'text': extraction.extraction_text,
                    'attributes': extraction.attributes or {},
                    'confidence': getattr(extraction, 'confidence', 1.0)
                })

            # Calculate processing time
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()

            # Create summary statistics
            class_counts = {}
            for ext in extractions:
                class_name = ext['class']
                class_counts[class_name] = class_counts.get(class_name, 0) + 1

            return {
                'task_id': task_id,
                'status': 'completed',
                'extractions': extractions,
                'metadata': {
                    'extraction_type': request.extraction_type,
                    'model_id': request.model_id,
                    'text_length': len(request.text),
                    'extraction_count': len(extractions),
                    'class_distribution': class_counts,
                    'timestamp': start_time.isoformat()
                },
                'processing_time': processing_time
            }

        except Exception as e:
            logger.error(f"Entity extraction error: {e}")
            return {
                'task_id': task_id,
                'status': 'error',
                'error': str(e),
                'processing_time': (datetime.now() - start_time).total_seconds()
            }

    async def extract_from_transcription(self, transcription_data: Dict) -> Dict:
        """Extract entities from audio transcription data"""
        # Combine transcription text
        text_parts = []

        if 'text' in transcription_data:
            text_parts.append(transcription_data['text'])

        if 'chunks' in transcription_data:
            for chunk in transcription_data['chunks']:
                if 'text' in chunk:
                    text_parts.append(chunk['text'])

        combined_text = " ".join(text_parts)

        if not combined_text.strip():
            return {'error': 'No text found in transcription data'}

        # Extract entities with media focus
        request = EntityExtractionRequest(
            text=combined_text,
            extraction_type="media",
            model_id="gemini-2.0-flash-exp"
        )

        return await self.extract_entities(request)

    def get_available_templates(self) -> Dict[str, str]:
        """Get available extraction templates"""
        return {
            name: template["prompt"].strip()[:200] + "..."
            for name, template in self.extraction_templates.items()
        }

# Global extractor instance
extractor = EntityExtractor()

@app.post("/extract")
async def extract_entities(request: EntityExtractionRequest):
    """Extract entities from text"""
    try:
        result = await extractor.extract_entities(request)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Extraction endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/extract-from-transcription")
async def extract_from_transcription(transcription_data: Dict[str, Any]):
    """Extract entities from transcription data"""
    try:
        result = await extractor.extract_from_transcription(transcription_data)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Transcription extraction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/extract-from-file")
async def extract_from_file(
    file: UploadFile = File(...),
    extraction_type: str = "general",
    model_id: str = "gemini-2.0-flash-exp"
):
    """Extract entities from uploaded text file"""
    try:
        content = await file.read()
        text = content.decode('utf-8')

        request = EntityExtractionRequest(
            text=text,
            extraction_type=extraction_type,
            model_id=model_id
        )

        result = await extractor.extract_entities(request)
        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"File extraction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/templates")
async def get_templates():
    """Get available extraction templates"""
    return {
        "templates": extractor.get_available_templates(),
        "default_model": "gemini-2.0-flash-exp"
    }

@app.post("/batch-extract")
async def batch_extract(
    texts: List[str],
    extraction_type: str = "general",
    model_id: str = "gemini-2.0-flash-exp"
):
    """Extract entities from multiple texts"""
    if len(texts) > 10:  # Limit batch size
        raise HTTPException(status_code=400, detail="Maximum 10 texts per batch")

    results = []
    for i, text in enumerate(texts):
        request = EntityExtractionRequest(
            text=text,
            extraction_type=extraction_type,
            model_id=model_id
        )

        result = await extractor.extract_entities(request)
        result['batch_index'] = i
        results.append(result)

    return {"batch_results": results}

@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "langextract_available": LANGEXTRACT_AVAILABLE,
        "api_key_configured": bool(extractor.api_key),
        "available_templates": list(extractor.extraction_templates.keys())
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8004, log_level="info")

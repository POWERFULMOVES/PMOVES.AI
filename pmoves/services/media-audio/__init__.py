"""Media-Audio Analyzer service.

STATUS: implemented (v1). Entry point: ``server:app`` (FastAPI).
Pipeline: STT (whisper-large-v3-turbo) + speaker diarization (pyannote 3.1, gated
on HF_TOKEN) + speech-emotion (hubert) + librosa acoustic features.
Backend is env-selected via MEDIA_BACKEND (transformers implemented; nemo/vulkan TODO).
See server.py and project_media_stack_roadmap.
"""

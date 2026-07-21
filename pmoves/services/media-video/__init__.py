"""Media-Video Analyzer service.

STATUS: implemented (v1). Entry point: ``server:app`` (FastAPI).
Pipeline: OpenCV frame sampling -> object detection via facebook/detr-resnet-50
(Apache; replaces AGPL YOLO). Backend env-selected via MEDIA_BACKEND (transformers
implemented; nemo/vulkan TODO). See server.py and project_media_stack_roadmap.
"""

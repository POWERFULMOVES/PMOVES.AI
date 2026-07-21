"""Media-Video Analyzer service.

STATUS: implemented (v1). Entry point: ``server:app`` (FastAPI).
Pipeline: OpenCV frame sampling -> object detection. Detector is operator-selectable
via DETECTION_ENGINE: "detr" (facebook/detr-resnet-50, Apache, default, ships anywhere)
or "yolo" (Ultralytics, AGPL — fine to run privately / on Jetson). Backend env-selected
via MEDIA_BACKEND (transformers implemented; nemo/vulkan TODO). Exposes /topology for
network-awareness self-report. See server.py and project_media_stack_roadmap.
"""

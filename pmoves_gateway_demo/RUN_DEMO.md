# PMOVES Gateway Demo

## Install
pip install -r requirements-demo.txt

## Run
uvicorn gateway.main:app --reload

## Try
- http://localhost:8000/demo/shapes-webrtc (open in two tabs)
- http://localhost:8000/web/client.html

## APIs
POST /geometry/event
POST /geometry/decode/text
POST /geometry/calibration/report
GET  /shape/point/{id}/jump

.PHONY: run demo test docker deps

run:
	uvicorn pmoves.services.gateway.gateway.main:app --reload --port 8085

deps:
	pip install -r requirements.txt

demo:
	python scripts/mini_geometry_decode.py

test:
	pytest -q

docker:
	docker build -f Dockerfile -t pmoves-gateway . && docker run --rm -p 8085:8085 pmoves-gateway

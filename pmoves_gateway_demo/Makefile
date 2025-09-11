.PHONY: run demo test docker

run:
\tuvicorn gateway.main:app --reload

demo:
\tpython scripts/mini_geometry_decode.py

test:
\tpytest -q

docker:
\tdocker build -f Dockerfile.demo -t pmoves-demo . && docker run --rm -p 8000:8000 pmoves-demo

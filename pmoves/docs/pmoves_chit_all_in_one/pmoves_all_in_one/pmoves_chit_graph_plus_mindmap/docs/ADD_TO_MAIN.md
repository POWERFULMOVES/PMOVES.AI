# Register the MindMap router in the FastAPI gateway

1. **Confirm the router module is present.**
   - The gateway demo now ships with `pmoves_gateway_demo/gateway/api/mindmap.py`, copied from the reference implementation in `pmoves/docs/pmoves_chit_all_in_one/pmoves_all_in_one/pmoves_chit_graph_plus_mindmap/gateway/api/mindmap.py`.
   - If you are wiring the MindMap router into a different FastAPI service, copy or adapt that file so it exposes a FastAPI `router` defining `/mindmap/{constellation_id}`.

2. **Ensure the FastAPI app imports the router.**
   - `pmoves_gateway_demo/gateway/main.py` already contains the import:
     ```python
     from gateway.api.mindmap import router as mindmap_router
     ```
   - For other services, add the same import alongside the existing router imports.

3. **Attach the router to the application.**
   - The demo app registers the router with:
     ```python
     app.include_router(mindmap_router)
     ```
   - Apply the same inclusion order when you port the router elsewhere, then restart Uvicorn so the route is available.

4. **Install the Neo4j driver.**
   - The `pmoves_gateway_demo/requirements-demo.txt` file now lists `neo4j`, so running `pip install -r requirements-demo.txt` installs the driver.
   - If another service manages dependencies separately, be sure to add a compatible `neo4j` package entry.

## How to verify the integration

1. **Manual smoke test.**
   - From the project root:
     ```bash
     cd pmoves_gateway_demo
     pip install -r requirements-demo.txt
     uvicorn gateway.main:app --reload --port 8000
     ```
   - With the service running, query the new endpoint using the provided helper script:
     ```bash
     python ../pmoves/docs/pmoves_chit_all_in_one/pmoves_all_in_one/pmoves_chit_graph_plus_mindmap/scripts/mindmap_query.py \
       --base http://localhost:8000 \
       --cid <constellation_id>
     ```
     Replace `<constellation_id>` with a constellation that exists in your Neo4j instance. The script should print a JSON payload containing `items`.
   - Alternatively, make a direct request:
     ```bash
     curl "http://localhost:8000/mindmap/<constellation_id>?modalities=text&minProj=0.5&minConf=0.5&limit=10"
     ```
     A `200 OK` with a populated JSON body confirms the router is wired in.

2. **API documentation check.**
   - Visit `http://localhost:8000/docs` and confirm a **MindMap** tag appears with the `/mindmap/{constellation_id}` operation.

3. **Regression tests (optional but recommended).**
   - While still in `pmoves_gateway_demo/`, run the existing suite to ensure the import did not break other endpoints:
     ```bash
     pytest -q
     ```
   - All tests should pass; investigate any failures before promoting the change.

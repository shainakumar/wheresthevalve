# Valve POC (Brick + SPARQL + NetworkX)

- `brick/uva_schema.ttl` — minimal UVA extension (domains + valve properties)
- `graph/olsson_instances.ttl` — building instances (rooms, valves, feeds)
- `queries/*.rq` — SPARQL templates
- `app/*.py` — hybrid engine + CLI (`python app/ui.py`)

**Run**
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app/ui.py
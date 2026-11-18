# archive

Code from the original day-1 app, kept for reference. Nothing in the app, tests, CI or Docker image imports it.

- render.yaml, docker-compose.yml: the old Render + Postgres deployment
- backend/database.py, backend/models.py: SQLAlchemy/Postgres layer (borders table, query log)
- backend/query.py: the old agent (model-guessed regions, years and moments)
- backend/retrieve.py, backend/ingest.py: the original MiniLM retrieval and 500-char chunk ingest
- backend/seed_borders.py: loaded historical-basemaps into Postgres
- historical-basemaps-master/: aourednik/historical-basemaps snapshots (GPL-3), replaced by CShapes 2.0

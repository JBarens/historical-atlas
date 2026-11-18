# Frontend phase

## Decisions (Jasper)
1. API wired to the practicum pipeline: `POST /api/ask {question, history}` calls `pipeline.answer()`. The old
   `/query` (old `retrieve()` + agent, fake 12 ms/char SSE), `/borders`, `/history` and `/country` are removed; no
   Postgres for serving. `backend/database.py`, `models.py`, `query.py`, `retrieve.py`, `seed_borders.py` are no longer
   imported by the app (kept in the repo).
2. Map: MapLibre GL + OpenFreeMap Positron tiles (no token). Driven only by the case: static GeoJSON of the five
   dispute areas, `backend/data/static/cases.geojson` (hand-drawn approximate polygons, provenance in the file). No case
   = Europe view. No LLM output drives the map.
3. Sources: footnote markers per claim; a click opens a side panel with the passage highlighted in its document
   context, speaker, date, source, title and doc id. Tool claims: `calc` (tool input/output). Conversation claims:
   `earlier`.
4. Statuses: answered / insufficient_evidence / needs_clarification / error (clean message + request id). The request id
   is shown small under every answer.
5. No token streaming: progress steps during the real wait, then a fixed 1 s reveal of the validated answer.
6. Safe rendering: everything is React text nodes; no `dangerouslySetInnerHTML`/`innerHTML` (asserted in
   `backend/tests/test_api.py`).
7. Access and cost: demo mode replays `backend/data/static/demo_conversations.json` (5 conversations, 7 real pipeline
   turns incl. one follow-up pair and one inflation calculation; generated once by `backend/scripts/generate_demo.py`
   for $0.080). Live mode needs `X-Invite-Code`; codes stored as sha256 in `INVITE_CODES_SHA256` with labels; limits
   5/min and 50/day per code; global `DAILY_SPEND_CAP_USD` (2.00) from the per-request cost; over the cap `/api/ask`
   returns 503 `daily_cap` and the UI drops back to demo mode. In-memory counters (single instance).
   `backend/scripts/make_invite_code.py` prints a new code once with its hash.
8. Hosting: Hugging Face Spaces (Docker, CPU), `Dockerfile` serves API + built frontend on 7860; deploy steps in the
   root README. Cold start: the UI shows a waking-up state until `/api/health` returns 200; the embedding model and
   index load at startup (background thread), the model is baked into the image.

## Hermes-made UX details
- Case detection (`backend/cases.py`): keywords in the rewritten query, question, then earlier user turns; fallback =
  majority case tag of the retrieved documents. The router has no `case` field, so this is code-only.
- Claims are attached to the answer sentence they overlap most (word overlap >= 0.35); unmatched claims are listed
  under the answer; duplicate markers per sentence are merged; out-of-range chunk ids show a grey `?`.
- Progress steps are timed client-side (0 / 2.5 / 5.5 s); demo playback uses the same steps and reveal.
- `?demo=N` deep link shows example N revealed; `&source=K` or `&source=calc` opens that panel (used for screenshots).
- Invite code is kept in localStorage; a 401 clears it.
- Layout: conversation left (40%), map right, source panel slides over the map.

## Screenshots (1440x900, headless Chrome)
`01_demo_start.png`, `02_demo_answer_source.png`, `03_demo_followup_calc.png`, `04_insufficient_petrich.png`,
`05_demo_mosul_map.png`, `06_waking.png`, `07_live_progress.png`, `08_live_answer.png`.

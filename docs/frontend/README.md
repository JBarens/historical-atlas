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


## Map data (frontend phase, round 2)

Jasper rejected the hand-drawn polygons and the historical-basemaps snapshots as too rough.

- Country borders: CShapes 2.0, Schvitz et al. 2022 (ETH Zurich), CC BY-NC-SA 4.0. backend/scripts/build_map_data.py
  keeps every state valid between 1914-01-01 and 1930-12-31, clips to Europe and the Middle East and simplifies with
  shared borders intact (~700 m). Output backend/data/static/borders.geojson (1.48 MB, 113 polygons, 109 label points),
  shared under the same licence. Each feature carries its first and last valid day, so the map draws the borders of the
  moment's date.
- Known CShapes gaps, shown instead of hidden:
  - Upper Silesia: CShapes places Katowice in Poland from 1919-06-28, so the June 1922 partition is not coded. The
    plebiscite area is drawn hatched as disputed until June 1922; the partition line appears from then.
  - Mosul: CShapes places Mosul and Kirkuk in Iraq from 1920-04-26. The vilayet is drawn hatched as disputed until the
    League Council decision of 16 Dec 1925.
  - Vilna: Polish from 1920-10-07 in CShapes, which matches the Zeligowski seizure.
  The timeline states this per moment ('borders as of <date> (CShapes); ... disputed until ...').
- Dispute areas (backend/data/static/cases.geojson, provenance per feature): Aland from Natural Earth admin-1 (public
  domain); Upper Silesia plebiscite area and Vilna region built from modern districts (geoBoundaries/OSM, ODbL),
  approximate; Mosul vilayet from modern Iraqi governorates (Natural Earth), approximate; Petrich from the geoBoundaries
  municipality (public domain), approximate.
- Moments (backend/data/static/moments.json): Hermes-curated, each with a corpus doc_id whose date was checked; a test
  enforces that every doc_id exists, is tagged with the case and is dated in the moment's year. Events the corpus does not
  cover (the 1921 Aland decision, the Oct 1925 Greco-Bulgarian incident, the Brussels line date) are left out.
- Demo conversations: dev-split questions that answered correctly in eval/results/rerank_depth_e2e_20.json, plus one
  deliberate insufficient_evidence example (Petrich) and the inflation calculation; one follow-up pair. Cost $0.12.

## Involved countries and zoom (round 3)

- Answer mentions (B, deterministic, no LLM): `backend/countries.py` maps 40 states (160 name patterns: historical names and
  adjectives, e.g. British/England -> United Kingdom, Ottoman/Turks -> Turkey, Iran -> Persia, Serb-Croat-Slovene ->
  Yugoslavia, dated where a name changes state) to CShapes names. Case-sensitive whole words in the validated answer
  and claim texts only, never the retrieved chunks; 'North Pole' and 'turkey' do not match. `/api/ask` returns
  `countries` [{name, count, in_map}]; the demo answers' `countries` are recomputed by
  `backend/scripts/add_demo_countries.py` (no API calls). Tests: `backend/tests/test_countries.py`.
- Moment actors (A): `actors` per moment in moments.json, Hermes-curated: only countries the moment's doc_id itself
  names in that role; empty when the document names none. A test checks each is a CShapes state valid on the date or
  outside the map.
- Map: dispute area strongest (rust); current moment's actors medium (blue tint + border, changes with the timeline);
  answer mentions soft tint. Countries outside the map show as 'Also involved: ...'.
- Zoom: the camera stays on the moment's focus. 'Show all' fits the dispute area plus all highlighted in-map countries
  (within the map bounds); pressing again or moving the timeline returns to the focus. Never automatic.
- Zoom-out limit: maxBounds = the borders data bbox (-12, 27, 52, 71), so the uncoloured area beyond the CShapes clip
  is never visible; minZoom 3. With the source panel open the map shrinks to the space left of the panel, so Mosul
  still fits.
- Screenshots 01-08 replaced; `09_mosul_show_all.png` shows 'Show all' active.

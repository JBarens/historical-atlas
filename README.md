---
title: Historical Atlas
sdk: docker
app_port: 7860
pinned: false
---

# Historical Atlas

Grounded question answering over British parliamentary debates (Hansard) and FRUS documents on five interwar
League of Nations disputes. Practicum brief and progress: docs/PRACTICUM_BRIEF.md, docs/PRACTICUM_PROGRESS.md.
Frontend and API decisions: docs/frontend/README.md.

## Run locally

```bash
cd frontend && npm ci && npm run build && cd ..
uv run -q --with anthropic --with python-dotenv --with fastembed --with numpy --with rank-bm25 --with fastapi \
  --with 'uvicorn[standard]' uvicorn main:app --app-dir backend --port 8000
# dev UI with hot reload (proxies /api to :8000): cd frontend && npm run dev
```

## Deploy to Hugging Face Spaces

1. Create a Space: SDK **Docker**, hardware **CPU basic** (free). This README's front matter sets `app_port: 7860`.
2. In Space settings, add secrets:
   - `ANTHROPIC_API_KEY`
   - `INVITE_CODES_SHA256`: comma-separated `label:sha256hex` entries. Create one with
     `uv run python backend/scripts/make_invite_code.py <label>` (the code is printed once; only the hash goes in the secret).
   - `DAILY_SPEND_CAP_USD` (default 2.00), optional `RATE_LIMIT_PER_MIN` (5) and `RATE_LIMIT_PER_DAY` (50).
3. Push this repo to the Space git remote (`git remote add space https://huggingface.co/spaces/<user>/<space>`;
   `git push space main`). The Space builds the Dockerfile (frontend build, embedding model baked in, ~1.7 GB image).
4. Check `https://<user>-<space>.hf.space/api/health` returns `{"status":"ok","live":true}`.

Without `INVITE_CODES_SHA256` the Space runs demo mode only. Counters and the spend total are in memory (one
instance); a restart resets them.

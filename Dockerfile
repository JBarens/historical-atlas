# Hugging Face Spaces (Docker, CPU): one container serves the FastAPI backend and the built frontend on :7860.
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
RUN useradd -m -u 1000 user
ENV HOME=/home/user PYTHONUNBUFFERED=1 FASTEMBED_CACHE_PATH=/home/user/fastembed FRONTEND_DIST=/app/frontend/dist \
    OBS_LOG_PATH=/tmp/requests.jsonl
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
# bake the embedding model into the image so a cold start does not download it
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('nomic-ai/nomic-embed-text-v1.5')" && chown -R user /home/user
COPY --chown=user backend/ backend/
COPY --chown=user eval/*.py eval/
COPY --from=web --chown=user /web/dist frontend/dist
USER user
EXPOSE 7860
CMD ["uvicorn", "main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "7860"]

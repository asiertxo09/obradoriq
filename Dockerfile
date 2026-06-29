# --- Stage 1: build the React frontend ---
FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build      # -> /build/dist

# --- Stage 2: python runtime serving API + static frontend ---
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# Preserve the repo layout the code expects: /app/{backend,frontend,data}
COPY backend/ /app/backend/
COPY data/ /app/data/
COPY --from=frontend /build/dist /app/frontend/dist

WORKDIR /app/backend
RUN pip install --no-cache-dir -e .

# Render provides $PORT; default to 8000 locally.
ENV PORT=8000 SEED_ON_START=true LLM_OFFLINE=true
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]

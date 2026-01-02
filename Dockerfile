
# Stage 1: Build Frontend
FROM node:18-alpine as frontend-builder

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
# Copy .env to parent dir (/app/.env) because vite config expects envDir: '..'
COPY .env /app/.env
RUN npm run build

# Stage 2: Build Backend & Serve
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (e.g. for audio/image processing if needed)
# RUN apt-get update && apt-get install -y ...

# Install python dependencies
COPY pyproject.toml uv.lock ./
RUN pip install uv && \
    uv pip install --system --no-cache -r pyproject.toml

# Copy backend code
COPY backend ./backend

# Copy built frontend from Stage 1 to a directory the backend can serve
# We will serve from /app/static
COPY --from=frontend-builder /app/frontend/dist ./static

# Expose port (Cloud Run sets PORT env var, default 8080)
ENV PORT=8080
EXPOSE 8080

# Command to run the app
CMD ["sh", "-c", "uvicorn backend.api.main:app --host 0.0.0.0 --port ${PORT}"]

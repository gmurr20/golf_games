# Stage 1: Build the React frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# Stage 2: Build and run the Flask backend
FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend source
COPY backend/ ./backend/

# Copy built frontend assets from stage 1
# app.py resolves dist at ../frontend/dist relative to the backend dir,
# which maps to /app/frontend/dist inside the container.
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

EXPOSE 8080

CMD sh -c 'gunicorn --chdir backend "app:create_app()" --bind 0.0.0.0:${PORT:-8080}'

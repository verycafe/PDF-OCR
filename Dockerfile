FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim

WORKDIR /app

# Runtime/build env for PaddleX model caching
ENV FLASK_ENV=production \
    PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True \
    PADDLE_PDX_CACHE_HOME=/app/.paddlex

# System dependencies for PaddleOCR and DOC/DOCX -> PDF conversion
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libgomp1 \
    libreoffice-writer \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .

# Install CPU-only PyTorch first (saves ~2GB vs full version)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install PaddlePaddle CPU version explicitly
RUN pip install --no-cache-dir "paddlepaddle>=3.2.0,<3.4.0"

# Install remaining dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Preload OCR/structure models into the image so runtime startup does not
# need to download them on first use.
COPY scripts/preload-models.py ./scripts/preload-models.py
RUN mkdir -p /app/data/uploads /app/.paddlex
RUN python scripts/preload-models.py

# Copy application code
COPY config.py run.py ./
COPY app/ ./app/
COPY --from=frontend-builder /frontend/dist ./frontend/dist

# Railway provides PORT env var
EXPOSE 5001

CMD ["python", "run.py"]

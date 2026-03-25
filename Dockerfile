FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim

WORKDIR /app

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

# Copy application code
COPY config.py run.py ./
COPY app/ ./app/
COPY --from=frontend-builder /frontend/dist ./frontend/dist

# Create data directory
RUN mkdir -p /app/data/uploads

# Railway provides PORT env var
ENV FLASK_ENV=production
ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
EXPOSE 5001

CMD ["python", "run.py"]

FROM python:3.11-slim

WORKDIR /app

# System dependencies for PaddleOCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .

# Install CPU-only PyTorch first (saves ~2GB vs full version)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install PaddlePaddle CPU version explicitly
RUN pip install --no-cache-dir paddlepaddle

# Install remaining dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Build frontend
COPY frontend/dist /app/frontend/dist

# Copy application code
COPY config.py run.py ./
COPY app/ ./app/

# Create data directory
RUN mkdir -p /app/data/uploads

# Railway provides PORT env var
ENV FLASK_ENV=production
EXPOSE 5001

CMD ["python", "run.py"]

FROM python:3.10-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    libopenblas-dev \
    cmake \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install requirements to a temporary location
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.10-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libopenblas-base \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy the application code
COPY . .

# Expose port
EXPOSE 8000

# Production Environment Variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV AI_BACKEND=ollama
ENV OLLAMA_HOST=http://ollama:11434
ENV OLLAMA_MODEL=gemma:2b

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run as non-root user for security
RUN useradd -m lahuta && chown -R lahuta:lahuta /app
USER lahuta

# Run the server
CMD ["python", "api/server.py"]

FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir uv && uv pip install --system -e "."

# Copy source
COPY src/ src/
COPY config/ config/

# Default command
CMD ["python", "-m", "flow", "generate", "--help"]

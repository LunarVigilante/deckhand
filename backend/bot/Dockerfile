# Multi-stage build for production optimization
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Development stage
FROM base as development
COPY . .
CMD ["python", "main.py"]

# Production stage
FROM base as production

# Create non-root user for security
RUN groupadd -r botuser && useradd -r -g botuser botuser

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p /app/logs && chown -R botuser:botuser /app

# Switch to non-root user
USER botuser

# Health check - check if bot process is running and responsive
HEALTHCHECK --interval=60s --timeout=30s --start-period=10s --retries=3 \
    CMD python -c "import psutil; import sys; sys.exit(0 if any('python' in p.name() and 'main.py' in ' '.join(p.cmdline()) for p in psutil.process_iter(['name', 'cmdline'])) else 1)" || exit 1

# Run the bot
CMD ["python", "main.py"]
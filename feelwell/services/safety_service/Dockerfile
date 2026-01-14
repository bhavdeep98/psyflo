# Safety Service Dockerfile
# Layer 1 defense - deterministic guardrails per ADR-001
#
# Build: docker build -t feelwell-safety-service .
# Run:   docker run -p 8001:8001 feelwell-safety-service

FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8001

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash appuser

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared modules
COPY ../../shared /app/feelwell/shared/

# Copy service code
COPY . /app/feelwell/services/safety_service/

# Create __init__.py files for package structure
RUN touch /app/feelwell/__init__.py && \
    touch /app/feelwell/services/__init__.py

# Change ownership to non-root user
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Expose port
EXPOSE ${PORT}

# Run with gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:8001", "--workers", "2", "--threads", "4", \
     "--timeout", "30", "--access-logfile", "-", "--error-logfile", "-", \
     "feelwell.services.safety_service.handler:app"]

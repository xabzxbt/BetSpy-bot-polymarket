# Build stage
FROM python:3.12-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Ensure proper permissions for botuser to access packages
RUN chmod -R 755 /usr/local/lib/python3.12/site-packages
RUN chmod -R 755 /usr/local/bin

# Create logs directory
RUN mkdir -p /app/logs

# Copy application code (all .py files + subdirectories)
COPY *.py .
COPY services/ ./services/
COPY locales/ ./locales/
COPY migrations/ ./migrations/
COPY analytics/ ./analytics/

# Create non-root user for security
RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app
USER botuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import asyncio; asyncio.run(__import__('aiohttp').ClientSession().get('https://data-api.polymarket.com/'))" || exit 1

# Run the bot
CMD ["python", "main.py"]
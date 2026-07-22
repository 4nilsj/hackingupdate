FROM python:3.12-slim

LABEL maintainer="Anil Kumar Jamadar"
LABEL description="HackingUpdate — AI-powered daily security intelligence briefing"

# Set working directory
WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY hackingupdate/ ./hackingupdate/
COPY scripts/ ./scripts/
COPY feeds/ ./feeds/

# Install the package
RUN pip install --no-cache-dir -e .

# Create runtime directories
RUN mkdir -p cache reports logs data

# Healthcheck: verify the package is importable and data dir exists
HEALTHCHECK --interval=60s --timeout=5s --retries=3 \
  CMD python -c "from hackingupdate.config import DB_PATH; assert DB_PATH.parent.exists()"

# Default command: run the full pipeline
CMD ["hackingupdate", "run"]

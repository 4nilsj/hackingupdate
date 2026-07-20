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
COPY config.py ./

# Install the package
RUN pip install --no-cache-dir -e .

# Create runtime directories
RUN mkdir -p cache reports logs data

# Default command: run the full pipeline
CMD ["hackingupdate", "run"]

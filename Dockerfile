FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    default-jdk \
    libmagic1 \
    build-essential \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Java for PySpark
ENV JAVA_HOME=/usr/lib/jvm/default-java
ENV PATH="${JAVA_HOME}/bin:${PATH}"

# Python environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_TIMEOUT=300

WORKDIR /app

# Install dependencies first
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt


COPY . .

# Create media directories
RUN mkdir -p /app/media/uploads /app/media/results

EXPOSE 8000
# ==========================
# Base image: Airflow 2.10.4 with Python 3.11 (Latest stable)
# ==========================
FROM apache/airflow:2.10.4-python3.11

# ==========================
# Switch to root to install system dependencies
# ==========================
USER root

# Install system dependencies for GDAL / Rasterio
# Also install build tools required to compile Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        curl \
        ca-certificates \
        gdal-bin \
        libproj-dev \
        libgeos-dev \
        libgeos++-dev \
        libgeos-c1v5 \
        libgeos++-dev \
    && rm -rf /var/lib/apt/lists/*

# Set GDAL / PROJ environment variables for runtime
ENV GDAL_DATA=/usr/share/gdal \
    PROJ_LIB=/usr/share/proj

# ==========================
# Switch back to airflow user
# ==========================
USER airflow

# ==========================
# Copy only requirements to leverage Docker cache
# ==========================
COPY requirements.txt /tmp/requirements.txt

# Upgrade pip and install Python dependencies
RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r /tmp/requirements.txt

# ==========================
# Set working directory
# ==========================
WORKDIR /opt/airflow

# ==========================
# Create necessary directories
# ==========================
RUN mkdir -p /opt/airflow/fip
RUN mkdir -p /opt/airflow/fip/downloads
RUN mkdir -p /opt/airflow/logs
RUN mkdir -p /opt/airflow/styles

# ==========================
# Set environment variables
# ==========================
ENV PYTHONPATH=/opt/airflow/fip
ENV AIRFLOW__CORE__EXECUTOR=LocalExecutor
ENV AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=true
ENV AIRFLOW__CORE__LOAD_EXAMPLES=false
ENV AIRFLOW__API__AUTH_BACKENDS=airflow.api.auth.backend.basic_auth

# ==========================
# Initialize Airflow database during build
# ==========================
# Note: Database initialization will be done at runtime when container starts
# This ensures the database is available before Airflow tries to connect

# ==========================
# Note:
# - DAGs and project code will be mounted via docker-compose volumes
# - No need to COPY dags/ or fip/ here
# - This allows dynamic updates and avoids build errors
# ==========================

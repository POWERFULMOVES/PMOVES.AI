# PMOVES Shared CUDA Base Image
# ==============================
# Base image for all GPU-accelerated PMOVES services.
# Reduces image duplication and ensures consistent CUDA setup.
#
# Build: docker build -t pmoves/cuda-base:12.8.1 .
# Usage: FROM pmoves/cuda-base:12.8.1

FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04

LABEL maintainer="PMOVES <pmoves@powerfulmoves.ai>"
LABEL description="Shared CUDA base image for PMOVES GPU services"
LABEL version="12.8.1"

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install Python 3.11 and common dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip \
    curl \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set Python 3.11 as default
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Upgrade pip
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel

# Create non-root user for security
RUN useradd -m -u 65532 -s /bin/bash pmoves

# CUDA optimization environment variables
ENV CUDA_MODULE_LOADING=LAZY \
    PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:4096 \
    TORCH_CUDNN_V8_API_ENABLED=1 \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility

# Set working directory
WORKDIR /app

# Default to non-root user
USER pmoves

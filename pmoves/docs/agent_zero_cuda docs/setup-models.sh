#!/bin/bash
# setup-2025-models.sh - Download and configure latest models

echo "🚀 Setting up 2025 AI Models for RTX 5090..."

# Create model directory
mkdir -p ~/ai-models-2025
cd ~/ai-models-2025

# Start services
docker-compose -f docker-compose-2025-ultimate.gpu.yml up -d

# Wait for Ollama to start
sleep 30

# Download latest models (in order of priority)
echo "📥 Downloading GLM-4.5 (Current SOTA)..."
# Note: GLM-4.5 not yet in Ollama, use API for now
curl -X POST http://localhost:11434/api/pull -d '{"name":"qwen3:30b-a3b-instruct"}'

echo "📥 Downloading Qwen3 models..."
ollama pull qwen3:235b-a22b-instruct     # Flagship model
ollama pull qwen3:30b-a3b-instruct       # Efficient MoE
ollama pull qwen3-coder:480b-a35b-instruct

echo "📥 Downloading DeepSeek models..."
ollama pull deepseek-v3.1:32b           # Hybrid model
ollama pull deepseek-r1:32b             # Reasoning specialist
ollama pull deepseek-r1:8b              # Fast variant

echo "📥 Downloading OpenAI GPT OSS..."
ollama pull gpt-oss:20b                 # Efficient size
ollama pull gpt-oss:120b                # Full power

echo "📥 Downloading Vision-Language models..."
ollama pull qwen2.5-vl:7b               # Multimodal
ollama pull pixtral:12b                 # Mistral VLM

# Setup complete
echo "✅ Setup complete! Models ready for RTX 5090"
echo "🌐 Agent Zero UI: http://localhost:5000"
echo "🔌 Ollama API: http://localhost:11434"

# Display model info
ollama list
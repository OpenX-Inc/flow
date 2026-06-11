#!/bin/bash
# Deploy the GPU backend to Modal
# Usage: ./scripts/deploy_modal.sh

set -e

echo "=== Deploying Flow GPU Backend to Modal ==="

# Check modal CLI is installed
if ! command -v modal &> /dev/null; then
    echo "Error: modal CLI not installed. Run: pip install modal"
    exit 1
fi

# Deploy
modal deploy src/gpu_backend/modal_server.py

echo ""
echo "=== Deployment complete ==="
echo "Run 'modal serve src/gpu_backend/modal_server.py' for development"

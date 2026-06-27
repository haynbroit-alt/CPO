#!/usr/bin/env bash
# Build all world-specific sandbox images.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORLDS_DIR="$SCRIPT_DIR/worlds"

declare -A WORLDS=(
  [llm]="$SCRIPT_DIR/../sandbox/Dockerfile"
  [symbolic]="$WORLDS_DIR/Dockerfile.symbolic"
  [neuro]="$WORLDS_DIR/Dockerfile.neuro"
  [bayesian]="$WORLDS_DIR/Dockerfile.bayesian"
  [evolutionary]="$WORLDS_DIR/Dockerfile.evolutionary"
  [formal]="$WORLDS_DIR/Dockerfile.formal"
  [multimodal]="$WORLDS_DIR/Dockerfile.multimodal"
)

for world in "${!WORLDS[@]}"; do
  dockerfile="${WORLDS[$world]}"
  tag="proof-protocol/${world}:latest"
  echo "==> Building $tag from $dockerfile"
  docker build -f "$dockerfile" -t "$tag" "$(dirname "$dockerfile")"
done

echo ""
echo "All world images built successfully."
docker images | grep "proof-protocol/"

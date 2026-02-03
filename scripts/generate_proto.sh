#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)/src/ee_smarthub/proto"
VERSION="${1:-1-4}"

mkdir -p "$OUTPUT_DIR"

TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

# Official Broadband Forum USP specification repository
REPO_URL="https://raw.githubusercontent.com/BroadbandForum/usp/v1.4.2/specification"

if ! python -c "import grpc_tools.protoc" &> /dev/null; then
    echo "grpc_tools.protoc is not installed. Please install it with 'pip install grpcio-tools'." >&2
    exit 1
fi

if ! command -v protoc-gen-python_betterproto2 &> /dev/null; then
    echo "protoc-gen-python_betterproto2 is not installed. Please install it with 'pip install betterproto2_compiler'." >&2
    exit 1
fi

echo "=================================================="
echo "USP Python Code Generator"
echo "=================================================="
echo "USP version: $VERSION"
echo ""

cd "$TEMP_DIR"

PROTO_FILES=(
    "usp-msg-$VERSION.proto"
    "usp-record-$VERSION.proto"
)

for PROTO_FILE in "${PROTO_FILES[@]}"; do
    echo "Downloading $PROTO_FILE..."
    curl -sSf "$REPO_URL/$PROTO_FILE" -o "$PROTO_FILE"
done

echo "Generating Python code from proto files..."
python -m grpc_tools.protoc \
    -I . \
    --python_betterproto2_out="$OUTPUT_DIR" \
    "${PROTO_FILES[@]}"

echo "Python code generated successfully in $OUTPUT_DIR"
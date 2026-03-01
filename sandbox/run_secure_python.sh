#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <script.py> [image-name]"
    exit 1
fi

SCRIPT_PATH="$1"
IMAGE_NAME="${2:-secure-python}"

if [[ ! -f "${SCRIPT_PATH}" ]]; then
    echo "Script not found: ${SCRIPT_PATH}"
    exit 1
fi

ABS_SCRIPT_PATH="$(cd "$(dirname "${SCRIPT_PATH}")" && pwd)/$(basename "${SCRIPT_PATH}")"

timeout 10s docker run --network none --init --rm \
    --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=64m \
    --cap-drop=ALL \
    --security-opt no-new-privileges \
    --memory=256m --memory-swap=256m --cpus="0.5" \
    --pids-limit=128 \
    --ulimit nproc=128:128 --ulimit stack=67108864 \
    --user 65534:65534 \
    -v "${ABS_SCRIPT_PATH}:/sandbox/script.py:ro" \
    "${IMAGE_NAME}" /sandbox/script.py

#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <base|science>"
    exit 1
fi

PROFILE="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "${PROFILE}" in
    base)
        DOCKERFILE="${SCRIPT_DIR}/secure_python.Dockerfile"
        IMAGE_NAME="secure-python"
        ;;
    science)
        DOCKERFILE="${SCRIPT_DIR}/secure_python_science.Dockerfile"
        IMAGE_NAME="secure-python-science"
        ;;
    *)
        echo "Unknown profile: ${PROFILE}"
        echo "Usage: $0 <base|science>"
        exit 1
        ;;
esac

docker build -t "${IMAGE_NAME}" -f "${DOCKERFILE}" "${SCRIPT_DIR}"

echo "Built image: ${IMAGE_NAME} (profile: ${PROFILE})"

#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")"

case "$(uname -m)" in
    arm64 | aarch64)
        build_arch="aarch64"
        platform="linux/arm64"
        ;;
    x86_64 | amd64)
        build_arch="amd64"
        platform="linux/amd64"
        ;;
    *)
        echo "Unsupported host architecture: $(uname -m)" >&2
        exit 1
        ;;
esac

image="needle-ha:test"
container="needle-ha-test"
test_dir="${PWD}/.test"
weights="${1:-}"

mkdir -p "${test_dir}/data" "${test_dir}/share"

if [[ -n "${weights}" ]]; then
    if [[ ! -f "${weights}" ]]; then
        echo "Weights file not found: ${weights}" >&2
        exit 1
    fi

    cp "${weights}" "${test_dir}/share/model.cact"
    printf '{"weights":"/share/model.cact"}\n' >"${test_dir}/data/options.json"
else
    printf '{"weights":""}\n' >"${test_dir}/data/options.json"
fi

docker rm --force "${container}" >/dev/null 2>&1 || true

echo "Building ${image} for ${platform}..."
docker build \
    --platform "${platform}" \
    --build-arg "BUILD_ARCH=${build_arch}" \
    --tag "${image}" \
    .

echo
echo "Starting Needle at http://localhost:7860"
echo "Press Ctrl+C to stop it."
docker run --rm \
    --name "${container}" \
    --publish 7860:7860 \
    --volume "${test_dir}/data:/data" \
    --volume "${test_dir}/share:/share" \
    "${image}"
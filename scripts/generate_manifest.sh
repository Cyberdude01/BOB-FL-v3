#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$ROOT/manifests"
find "$ROOT" -type f -not -path '*/.git/*' -printf '%P\t%s\n' | sort > "$ROOT/manifests/file-manifest.tsv"
sha256sum $(find "$ROOT" -type f -not -path '*/.git/*' | sort) > "$ROOT/manifests/sha256sums.txt"
echo "Wrote manifests/file-manifest.tsv and manifests/sha256sums.txt"

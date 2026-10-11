#!/usr/bin/env bash
# Link node, npm and npx in DIR (default ~/.local/bin) to this repository's shims.
set -euo pipefail

repo=$(cd "$(dirname "$0")" && pwd -P)
dir=${1:-$HOME/.local/bin}

for tool in node npm npx; do
  if [ -e "$dir/$tool" ] && [ ! -L "$dir/$tool" ]; then
    echo "nvm-shims: $dir/$tool exists and is not a symlink; move it away and run again" >&2
    exit 1
  fi
done

mkdir -p "$dir"
for tool in node npm npx; do
  ln -sfn "$repo/bin/$tool" "$dir/$tool"
  echo "linked $dir/$tool -> $repo/bin/$tool"
done

first=$(type -P node || true)
if [ "$first" = "$dir/node" ]; then
  echo "OK: $dir/node is the first node on PATH"
else
  echo "NOTE: ${first:-no node} comes before $dir/node on PATH; put $dir earlier in PATH, after nvm is loaded"
fi

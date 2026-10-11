#!/usr/bin/env bash
# Link node, npm and npx in DIR (default ~/.local/bin) to this repository's shims.
set -euo pipefail

repo=$(cd "$(dirname "$0")" && pwd -P)
dir=${1:-}
if [ -z "$dir" ]; then
  if [ -z "${HOME:-}" ]; then
    echo "nvm-shims: HOME is not set; pass the directory to link into" >&2
    exit 1
  fi
  dir=$HOME/.local/bin
fi

if [ "$(cd "$dir" 2>/dev/null && pwd -P)" = "$repo/bin" ]; then
  echo "nvm-shims: $dir is this repository's own bin directory; pick another directory" >&2
  exit 1
fi

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
case ":${PATH:-}:" in
  *":$dir:"*)
    if [ "$first" = "$dir/node" ]; then
      echo "OK: $dir/node is the first node on PATH"
    else
      echo "NOTE: ${first:-no node} comes before $dir/node on PATH; put $dir earlier in PATH, after nvm is loaded"
    fi
    ;;
  *)
    echo "NOTE: $dir is not on PATH; add it to PATH, after nvm is loaded"
    ;;
esac

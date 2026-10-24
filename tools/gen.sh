#!/usr/bin/env bash
# One image per call through Codex's image tool. Raw images and prompts stay in art/.
# usage: tools/gen.sh <out-name> "<prompt>" [reference images]
set -euo pipefail
cd "$(dirname "$0")/../art"; out="$1"; prompt="$2"; shift 2
rm -f "raw/$out.png"
refimg=(); for r in "$@"; do refimg+=(-i "$r"); done
printf '%s\n' "$prompt" > "logs/$out.prompt.txt"
codex exec --skip-git-repo-check -s workspace-write -C "$PWD/raw" "Use your image generation tool. Make one landscape image at the largest landscape size the tool supports (1536x1024). $prompt Save the final PNG as $out.png in the current directory and reply with just the path." ${refimg[@]+"${refimg[@]}"} < /dev/null > "logs/$out.log" 2>&1 || true
if [ -f "raw/$out.png" ]; then echo "ok $out"; else echo "FAILED $out: $(grep -o 'usage_limit_reached[^}]*' logs/$out.log | head -1)"; fi

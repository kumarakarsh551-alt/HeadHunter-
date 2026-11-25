#!/usr/bin/env bash
# One-shot mechanical port of the legacy sources into src/main/java.
#   usage: tools/port.sh <mojang client.txt for 1.19.2> <MCPConfig joined.tsrg for 1.19.2>
# Files that already exist in src/main/java (the hand-ported ones) are NEVER overwritten.
set -euo pipefail
cd "$(dirname "$0")/.."
[ $# -eq 2 ] || { sed -n '2,4p' "$0"; exit 1; }
rm -rf build/stage && mkdir -p build/stage
python3 tools/srg2mojmap.py --mojang "$1" --tsrg "$2" legacy-1.19.2-src build/stage
python3 tools/api_migrate_1_20.py build/stage
cp -rn build/stage/net/. src/main/java/net/
cp build/stage/MIGRATION_TODO.txt build/stage/unmapped_ids.txt . 2>/dev/null || cp build/stage/net/MIGRATION_TODO.txt . || true
echo "Done. Read MIGRATION_TODO.txt, then run: ./gradlew build"

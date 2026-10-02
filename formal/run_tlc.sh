#!/usr/bin/env bash
# Run TLA+ TLC model checker (Demo 5).
# Usage: ./run_tlc.sh safe   → runs MC_safe
#        ./run_tlc.sh broken → runs MC_broken
set -euo pipefail

MODEL="${1:-safe}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Find tla2tools.jar from the VS Code extension.
JAR=$(ls "C:/Users/Jethro/.vscode/extensions/tlaplus.vscode-ide-"*/out/tools/tla2tools.jar 2>/dev/null | head -1)

if [ -z "$JAR" ]; then
  echo "ERROR: tla2tools.jar not found."
  echo "Install the TLA+ VS Code extension, or set JAR manually:"
  echo "  JAR=/path/to/tla2tools.jar ./run_tlc.sh $MODEL"
  exit 1
fi

case "$MODEL" in
  safe)
    echo "=== Running MC_safe (all invariants should hold) ==="
    java -cp "$JAR" tlc2.TLC -config MC_safe.cfg MC_safe.tla
    ;;
  broken)
    echo "=== Running MC_broken (expect INV1 violation) ==="
    java -cp "$JAR" tlc2.TLC -config MC_broken.cfg MC_broken.tla
    ;;
  *)
    echo "Usage: $0 [safe|broken]"
    exit 1
    ;;
esac

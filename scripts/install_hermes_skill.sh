#!/usr/bin/env bash
# Install the visio-sentinel skill into Hermes Agent.
# Run from the visio-sentinel repo root.

set -euo pipefail

SKILL_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/skills/hermes/smart-home/visio-sentinel"
HERMES_SKILLS_DIR="${HERMES_SKILLS_DIR:-$HOME/.hermes/skills}"
TARGET_DIR="$HERMES_SKILLS_DIR/smart-home/visio-sentinel"

if [ ! -d "$HERMES_SKILLS_DIR" ]; then
  echo "Hermes skills directory not found: $HERMES_SKILLS_DIR"
  echo "Set HERMES_SKILLS_DIR env var or install Hermes Agent first."
  exit 1
fi

mkdir -p "$(dirname "$TARGET_DIR")"

if [ -L "$TARGET_DIR" ]; then
  echo "Skill already installed (symlink exists): $TARGET_DIR"
  echo "Remove it first with: rm $TARGET_DIR"
  exit 0
fi

ln -s "$SKILL_SRC" "$TARGET_DIR"
echo "Installed visio-sentinel skill for Hermes Agent:"
echo "  $TARGET_DIR -> $SKILL_SRC"
echo ""
echo "In Hermes, invoke with:  /visio-sentinel"

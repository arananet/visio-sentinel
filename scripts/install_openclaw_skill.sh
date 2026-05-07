#!/usr/bin/env bash
# Install the visio-sentinel skill into OpenClaw.
# Run from the visio-sentinel repo root.

set -euo pipefail

SKILL_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/skills/openclaw/visio-sentinel"
OPENCLAW_SKILLS_DIR="${OPENCLAW_SKILLS_DIR:-$HOME/.openclaw/workspace/skills}"
TARGET_DIR="$OPENCLAW_SKILLS_DIR/visio-sentinel"

if [ ! -d "$OPENCLAW_SKILLS_DIR" ]; then
  echo "OpenClaw skills directory not found: $OPENCLAW_SKILLS_DIR"
  echo "Set OPENCLAW_SKILLS_DIR env var or install OpenClaw first."
  exit 1
fi

if [ -L "$TARGET_DIR" ]; then
  echo "Skill already installed (symlink exists): $TARGET_DIR"
  echo "Remove it first with: rm $TARGET_DIR"
  exit 0
fi

ln -s "$SKILL_SRC" "$TARGET_DIR"
echo "Installed visio-sentinel skill for OpenClaw:"
echo "  $TARGET_DIR -> $SKILL_SRC"
echo ""
echo "In OpenClaw, invoke with:  /visio-sentinel"

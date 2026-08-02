#!/bin/bash
input=$(cat)

# Parse fields
MODEL=$(echo "$input" | jq -r '.model.display_name // "Claude"')
PCT=$(echo "$input" | jq -r '.context_window.used_percentage // 0' | cut -d. -f1)

# Git branch (fallback to jq data, then git command)
BRANCH=$(echo "$input" | jq -r '.git.branch // empty' 2>/dev/null)
if [ -z "$BRANCH" ]; then
  BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
fi

# Build progress bar (10 chars wide)
BAR_WIDTH=10
FILLED=$((PCT * BAR_WIDTH / 100))
EMPTY=$((BAR_WIDTH - FILLED))
BAR=$(printf "%${FILLED}s" | tr ' ' '▓')$(printf "%${EMPTY}s" | tr ' ' '░')

# Color based on threshold
if [ "$PCT" -ge 90 ]; then
  COLOR="\033[31m"  # red
elif [ "$PCT" -ge 70 ]; then
  COLOR="\033[33m"  # yellow
else
  COLOR="\033[32m"  # green
fi
RESET="\033[0m"

# Build output
OUTPUT="[${MODEL}] ${COLOR}${BAR} ${PCT}%${RESET}"

if [ -n "$BRANCH" ]; then
  OUTPUT="${OUTPUT}  |  ${BRANCH}"
fi

echo -e "$OUTPUT"

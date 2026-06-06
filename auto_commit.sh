#!/bin/bash
# =============================================================
# Auto Commit Script - Trade Lak Bot
# Checks for changes and commits/pushes if any found
# =============================================================

# Change to project directory
cd /root/trade_lak_bot || exit 1

# Setup gh auth for push
gh auth setup-git 2>/dev/null

# Check for changes
if [[ -z $(git status --porcelain) ]]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') | No changes detected. Skipping."
    exit 0
fi

# Get summary of changes
CHANGED_FILES=$(git status --short | wc -l)
SUMMARY=$(git status --short | head -5 | tr '\n' ', ' | sed 's/,$//')

# Stage all changes
git add -A

# Commit with timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
git commit -m "Auto-commit: ${CHANGED_FILES} file(s) changed at ${TIMESTAMP}

Changes: ${SUMMARY}"

# Push to remote
git push origin master 2>&1

echo "$(date '+%Y-%m-%d %H:%M:%S') | Committed and pushed ${CHANGED_FILES} file(s) successfully."

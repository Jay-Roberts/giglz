#!/bin/bash
set -e

changed=$(git diff --cached --name-status | grep -E "^[DR].*migrations/versions/" || true)

if [ -n "$changed" ]; then
    echo "ERROR: Cannot rename/delete migration files. Add new migrations instead."
    exit 1
fi

#!/bin/bash
# Post-edit hook: Auto-lint modified files
# This hook runs after Claude writes or edits a file

# Read tool input from stdin
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.filePath // empty' 2>/dev/null)

# Exit if no file path (shouldn't happen, but be safe)
if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Get the absolute path
if [[ "$FILE_PATH" != /* ]]; then
    FILE_PATH="$(pwd)/$FILE_PATH"
fi

# Skip if file doesn't exist (was deleted)
if [ ! -f "$FILE_PATH" ]; then
    exit 0
fi

# Determine file type and run appropriate linter
case "$FILE_PATH" in
    *.py)
        # Python files - run ruff
        if command -v ruff &> /dev/null; then
            cd "$(dirname "$FILE_PATH")"
            # Find the backend root (where pyproject.toml is)
            while [ ! -f "pyproject.toml" ] && [ "$(pwd)" != "/" ]; do
                cd ..
            done
            if [ -f "pyproject.toml" ]; then
                ruff check --fix "$FILE_PATH" 2>/dev/null || true
                ruff format "$FILE_PATH" 2>/dev/null || true
            fi
        fi
        ;;
    *.ts|*.tsx|*.js|*.jsx)
        # TypeScript/JavaScript files - run eslint if available
        if command -v npx &> /dev/null; then
            cd "$(dirname "$FILE_PATH")"
            # Find the frontend root (where package.json is)
            while [ ! -f "package.json" ] && [ "$(pwd)" != "/" ]; do
                cd ..
            done
            if [ -f "package.json" ]; then
                npx eslint --fix "$FILE_PATH" 2>/dev/null || true
            fi
        fi
        ;;
esac

# Always exit 0 - linting shouldn't block the workflow
exit 0

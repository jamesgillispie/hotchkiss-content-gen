#!/bin/bash

# Load environment variables from .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
else
    echo "Error: .env file not found."
    exit 1
fi

# Check for required environment variables
if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_SERVICE_ROLE_KEY" ] || [ -z "$OPENAI_API_KEY" ]; then
    echo "Error: Required environment variables are not set in .env file."
    echo "Please ensure the following variables are set:"
    echo "  - SUPABASE_URL"
    echo "  - SUPABASE_SERVICE_ROLE_KEY"
    echo "  - OPENAI_API_KEY"
    exit 1
fi

# Set default for OPENAI_API_BASE if not provided
if [ -z "$OPENAI_API_BASE" ]; then
    export OPENAI_API_BASE="https://api.openai.com/v1"
    echo "Using default OPENAI_API_BASE: $OPENAI_API_BASE"
fi

# Run the embedding script
echo "Starting embedding process..."
./embed_to_supabase.py

# Unset environment variables for security
if [ -f .env ]; then
    unset $(grep -v '^#' .env | sed -E 's/(.*)=.*/\1/' | xargs)
fi

echo "Embedding process completed."

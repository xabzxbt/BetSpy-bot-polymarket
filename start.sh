#!/bin/bash
set -e  # Exit on any error

echo "Starting Polymarket Whale Bot..."

# Check if required environment variables are set
if [ -z "$BOT_TOKEN" ]; then
    echo "Error: BOT_TOKEN environment variable is not set!"
    exit 1
fi

# Install dependencies if not already installed (for local testing)
if [ ! -f ".deps_installed" ] || [ "$(find .deps_installed -mmin +60)" ]; then
    echo "Installing dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    touch .deps_installed
fi

echo "Starting the bot..."
python main.py
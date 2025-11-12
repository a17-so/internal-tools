#!/bin/bash
# Setup script for followup-tool

set -e

echo "🚀 Setting up followup-tool..."
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.7+ first."
    exit 1
fi

echo "✓ Python found: $(python3 --version)"
echo ""

# Detect pip command (pip3 or pip)
if command -v pip3 &> /dev/null; then
    PIP_CMD="pip3"
elif command -v pip &> /dev/null; then
    PIP_CMD="pip"
else
    echo "❌ pip not found. Trying python3 -m pip..."
    PIP_CMD="python3 -m pip"
fi

echo "✓ Using: $PIP_CMD"
echo ""

# Install Python dependencies
echo "📦 Installing Python packages..."
$PIP_CMD install -r requirements.txt

echo ""
echo "🌐 Installing Playwright browser binaries..."
echo "   (This downloads Chromium - might take a minute)"
python3 -m playwright install chromium

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Test connection: python test_gmail_connection.py"
echo "  2. Dry run: python followup_gmail.py --dry-run"
echo "  3. Run it: python followup_gmail.py"


#!/bin/bash

# Test runner script for outreach tool
# Runs pytest with appropriate configuration and generates test report

set -e  # Exit on error

echo "========================================="
echo "Running Outreach Tool Test Suite"
echo "========================================="
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to project root
cd "$PROJECT_ROOT"

# Check if pytest is installed
if ! python3 -c "import pytest" 2>/dev/null; then
    echo "Error: pytest not installed"
    echo "Installing test dependencies..."
    pip3 install -q pytest pytest-timeout requests PyYAML
fi

# Check if required dependencies are installed
echo "Checking dependencies..."
if ! python3 -c "import flask" 2>/dev/null; then
    echo "Error: Flask not installed. Installing requirements..."
    pip3 install -q -r requirements.txt
fi

if ! python3 -c "import playwright" 2>/dev/null; then
    echo "Error: Playwright not installed. Installing..."
    pip3 install -q playwright
    python3 -m playwright install chromium
fi

echo "✓ Dependencies verified"
echo ""

# Set environment variables for testing
export TESTING=1

# Run pytest with verbose output
echo "Running tests..."
echo "---"
echo ""

# Run pytest with timeout and verbose output
python3 -m pytest tests/ \
    -v \
    --tb=short \
    --color=yes \
    -W ignore::DeprecationWarning \
    "$@"

TEST_EXIT_CODE=$?

echo ""
echo "========================================="
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "✓ All tests passed!"
    echo "========================================="
    exit 0
else
    echo "✗ Some tests failed"
    echo "========================================="
    exit $TEST_EXIT_CODE
fi

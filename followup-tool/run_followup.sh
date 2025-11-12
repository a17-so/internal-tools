#!/bin/bash
# Simple script to run the follow-up tool via API

# Default values
PROFILE="pretti"
MAX_EMAILS=""
DRY_RUN="false"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --profile)
            PROFILE="$2"
            shift 2
            ;;
        --max-emails)
            MAX_EMAILS="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN="true"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--profile pretti] [--max-emails N] [--dry-run]"
            exit 1
            ;;
    esac
done

# Build JSON payload
JSON_PAYLOAD="{"
JSON_PAYLOAD+="\"profile\":\"$PROFILE\""
if [ -n "$MAX_EMAILS" ]; then
    JSON_PAYLOAD+=",\"max_emails\":$MAX_EMAILS"
fi
if [ "$DRY_RUN" = "true" ]; then
    JSON_PAYLOAD+=",\"dry_run\":true"
fi
JSON_PAYLOAD+="}"

# Make API call
echo "🚀 Running follow-up tool..."
echo "   Profile: $PROFILE"
if [ -n "$MAX_EMAILS" ]; then
    echo "   Max emails: $MAX_EMAILS"
else
    echo "   Max emails: ALL"
fi
echo "   Dry run: $DRY_RUN"
echo ""

RESPONSE=$(curl -s -X POST http://localhost:8001/followup \
    -H "Content-Type: application/json" \
    -d "$JSON_PAYLOAD")

# Check if curl succeeded
if [ $? -ne 0 ]; then
    echo "❌ Error: Could not connect to API server"
    echo "   Make sure the API is running:"
    echo "   cd api && python3 -m flask --app index run --host 0.0.0.0 --port 8001"
    exit 1
fi

# Parse and display response
OK=$(echo "$RESPONSE" | grep -o '"ok":[^,]*' | cut -d: -f2)
if [ "$OK" = "true" ]; then
    MESSAGE=$(echo "$RESPONSE" | grep -o '"message":"[^"]*"' | cut -d'"' -f4)
    echo "✅ Success!"
    echo "   $MESSAGE"
else
    ERROR=$(echo "$RESPONSE" | grep -o '"error":"[^"]*"' | cut -d'"' -f4)
    echo "❌ Error: $ERROR"
    exit 1
fi


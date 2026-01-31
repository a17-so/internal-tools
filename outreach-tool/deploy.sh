#!/bin/bash

# Deployment script for outreach tool to Cloud Run
# This script deploys the updated code with validation and health check endpoints

set -e  # Exit on error

echo "========================================="
echo "Deploying Outreach Tool to Cloud Run"
echo "========================================="
echo ""

# Check we're in the right directory
if [ ! -f "Dockerfile" ]; then
    echo "Error: Must run from outreach-tool directory"
    exit 1
fi

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "Error: gcloud CLI not found. Install from https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Confirm deployment
echo "This will deploy the outreach tool with the following changes:"
echo "  ✓ Sender profile validation"
echo "  ✓ /health endpoint for monitoring"
echo "  ✓ /validate endpoint for debugging"
echo "  ✓ Improved error handling"
echo ""
read -p "Continue with deployment? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled"
    exit 0
fi

echo ""
echo "Starting deployment..."
echo ""

# Deploy to Cloud Run
gcloud run deploy outreach-tool-api \
  --source . \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --timeout 60 \
  --concurrency 8 \
  --min-instances 1 \
  --set-secrets GOOGLE_SERVICE_ACCOUNT_JSON=outreach-service-account:latest

echo ""
echo "========================================="
echo "Deployment Complete!"
echo "========================================="
echo ""

# Get the service URL
SERVICE_URL=$(gcloud run services describe outreach-tool-api --region us-central1 --format 'value(status.url)')

echo "Service URL: $SERVICE_URL"
echo ""

# Test the health endpoint
echo "Testing /health endpoint..."
echo "---"
curl -s $SERVICE_URL/health | python3 -m json.tool
echo ""
echo ""

# Test the validate endpoint
echo "Testing /validate endpoint..."
echo "---"
curl -s -X POST $SERVICE_URL/validate \
  -H "Content-Type: application/json" \
  -d '{"app": "hardmaxx", "sender_profile": "abhay"}' \
  | python3 -m json.tool
echo ""
echo ""

echo "========================================="
echo "Next Steps:"
echo "========================================="
echo "1. Test the endpoints from your iPhone Shortcut"
echo "2. Monitor logs: gcloud run logs read outreach-tool-api --region us-central1 --limit 50"
echo "3. Set up monitoring on /health endpoint"
echo ""

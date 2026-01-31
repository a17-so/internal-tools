#!/bin/bash

# Test script for new outreach tool endpoints
# Run this after restarting the Flask server

BASE_URL="http://localhost:8000"

echo "========================================="
echo "Testing Outreach Tool New Endpoints"
echo "========================================="
echo ""

# Test 1: Health Check
echo "1. Testing /health endpoint..."
echo "---"
curl -s $BASE_URL/health | python3 -m json.tool
echo ""
echo ""

# Test 2: Validate with valid config
echo "2. Testing /validate with valid sender profile..."
echo "---"
curl -s -X POST $BASE_URL/validate \
  -H "Content-Type: application/json" \
  -d '{"app": "hardmaxx", "sender_profile": "abhay", "category": "micro"}' \
  | python3 -m json.tool
echo ""
echo ""

# Test 3: Validate with invalid sender profile
echo "3. Testing /validate with invalid sender profile (should show error)..."
echo "---"
curl -s -X POST $BASE_URL/validate \
  -H "Content-Type: application/json" \
  -d '{"app": "hardmaxx", "sender_profile": "invalid_profile"}' \
  | python3 -m json.tool
echo ""
echo ""

# Test 4: Validate with missing app
echo "4. Testing /validate with missing app (should show error)..."
echo "---"
curl -s -X POST $BASE_URL/validate \
  -H "Content-Type: application/json" \
  -d '{}' \
  | python3 -m json.tool
echo ""
echo ""

# Test 5: Validate with different app
echo "5. Testing /validate with lifemaxx app..."
echo "---"
curl -s -X POST $BASE_URL/validate \
  -H "Content-Type: application/json" \
  -d '{"app": "lifemaxx", "sender_profile": "ethan"}' \
  | python3 -m json.tool
echo ""
echo ""

echo "========================================="
echo "Tests Complete!"
echo "========================================="
echo ""
echo "If you see 404 errors, the server needs to be restarted:"
echo "  1. Press Ctrl+C in the terminal running Flask"
echo "  2. Run: cd api && python3 -m flask --app index run --host 0.0.0.0 --port 8000"
echo "  3. Run this script again: bash test_new_endpoints.sh"
echo ""

#!/usr/bin/env python3
"""Quick test script for SearchAPI.io integration"""

import os
import sys
import time

# Set API key
os.environ["SEARCHAPI_KEY"] = "Ez42BbF8oTVFpNqrkvWhbacr"

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "api"))

from scrape_profile import scrape_tiktok_with_searchapi

def test_searchapi():
    print("Testing SearchAPI.io TikTok Profile API Integration\n")
    print("=" * 60)
    
    # Test 1: Basic profile scraping
    print("\n1. Testing @therock profile...")
    start = time.time()
    result = scrape_tiktok_with_searchapi("therock")
    elapsed = time.time() - start
    
    if "error" in result:
        print(f"   ❌ FAILED: {result['error']}")
    else:
        print(f"   ✅ SUCCESS in {elapsed:.2f}s")
        print(f"   - Name: {result.get('name')}")
        print(f"   - Username: {result.get('username')}")
        print(f"   - Followers: {result.get('followers'):,}")
        print(f"   - Bio: {result.get('bio', '')[:50]}...")
    
    # Test 2: Profile with @ symbol
    print("\n2. Testing @charlidamelio profile (with @ symbol)...")
    start = time.time()
    result = scrape_tiktok_with_searchapi("@charlidamelio")
    elapsed = time.time() - start
    
    if "error" in result:
        print(f"   ❌ FAILED: {result['error']}")
    else:
        print(f"   ✅ SUCCESS in {elapsed:.2f}s")
        print(f"   - Name: {result.get('name')}")
        print(f"   - Username: {result.get('username')}")
        print(f"   - Followers: {result.get('followers'):,}")
    
    # Test 3: Invalid username
    print("\n3. Testing invalid username...")
    start = time.time()
    result = scrape_tiktok_with_searchapi("this_user_definitely_does_not_exist_12345")
    elapsed = time.time() - start
    
    if "error" in result:
        print(f"   ✅ Correctly handled error in {elapsed:.2f}s: {result['error']}")
    else:
        print(f"   ⚠️  Unexpected success for invalid user")
    
    print("\n" + "=" * 60)
    print("✅ SearchAPI.io integration tests complete!")

if __name__ == "__main__":
    test_searchapi()

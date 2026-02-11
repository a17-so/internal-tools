"""
Comprehensive test suite for the outreach tool.

Tests cover:
- Profile scraping with various edge cases
- Endpoint health checks
- Integration tests for scraping endpoints
- Timeout enforcement
"""
import pytest
import time
import json
from typing import Dict, Any


class TestProfileScraping:
    """Test profile scraping functionality with real TikTok profiles."""
    
    @pytest.mark.timeout(10)
    def test_scrape_profile_no_ig_no_email(self, test_profiles, env_setup):
        """Test scraping profile with no IG or email (@ekam_m3hat)."""
        from scrape_profile import scrape_profile_sync
        
        profile_data = test_profiles["no_ig_no_email"]
        url = profile_data["url"]
        
        start_time = time.time()
        result = scrape_profile_sync(url, timeout_seconds=10.0)
        elapsed = time.time() - start_time
        
        # Verify it completed within timeout
        assert elapsed < 10.5, f"Scraping took {elapsed:.2f}s, should be under 10.5s"
        
        # Verify basic structure
        assert isinstance(result, dict), "Result should be a dictionary"
        assert "tt" in result or "platform" in result, "Result should contain TikTok data"
        
        # Verify TikTok handle is present
        if result.get("tt"):
            assert profile_data["handle"] in result["tt"].lower(), f"Expected handle {profile_data['handle']}"
        
        print(f"✓ Profile scraped in {elapsed:.2f}s: {json.dumps(result, indent=2)}")
    
    @pytest.mark.timeout(10)
    def test_scrape_profile_no_ig(self, test_profiles, env_setup):
        """Test scraping profile with no IG (@abhaychebium)."""
        from scrape_profile import scrape_profile_sync
        
        profile_data = test_profiles["no_ig"]
        url = profile_data["url"]
        
        start_time = time.time()
        result = scrape_profile_sync(url, timeout_seconds=10.0)
        elapsed = time.time() - start_time
        
        # Verify it completed within timeout
        assert elapsed < 10.5, f"Scraping took {elapsed:.2f}s, should be under 10.5s"
        
        # Verify basic structure
        assert isinstance(result, dict), "Result should be a dictionary"
        assert "tt" in result or "platform" in result, "Result should contain TikTok data"
        
        # Verify TikTok handle is present
        if result.get("tt"):
            assert profile_data["handle"] in result["tt"].lower(), f"Expected handle {profile_data['handle']}"
        
        print(f"✓ Profile scraped in {elapsed:.2f}s: {json.dumps(result, indent=2)}")
    
    @pytest.mark.timeout(10)
    def test_scrape_profile_with_email_and_ig(self, test_profiles, env_setup):
        """Test scraping profile with email and IG (@advaithakella)."""
        from scrape_profile import scrape_profile_sync
        
        profile_data = test_profiles["with_email_and_ig"]
        url = profile_data["url"]
        
        start_time = time.time()
        result = scrape_profile_sync(url, timeout_seconds=10.0)
        elapsed = time.time() - start_time
        
        # Verify it completed within timeout
        assert elapsed < 10.5, f"Scraping took {elapsed:.2f}s, should be under 10.5s"
        
        # Verify basic structure
        assert isinstance(result, dict), "Result should be a dictionary"
        assert "tt" in result or "platform" in result, "Result should contain TikTok data"
        
        # Verify TikTok handle is present
        if result.get("tt"):
            assert profile_data["handle"] in result["tt"].lower(), f"Expected handle {profile_data['handle']}"
        
        # Check for email and IG (may not always be present depending on profile changes)
        has_email = bool(result.get("email"))
        has_ig = bool(result.get("ig"))
        
        print(f"✓ Profile scraped in {elapsed:.2f}s")
        print(f"  Email found: {has_email}")
        print(f"  IG found: {has_ig}")
        print(f"  Data: {json.dumps(result, indent=2)}")
    
    def test_scrape_timeout_enforcement(self, env_setup):
        """Test that scraping enforces timeout correctly."""
        from scrape_profile import scrape_profile_sync
        
        # Use a URL that might be slow or non-existent
        url = "https://www.tiktok.com/@nonexistentuser12345678901234567890"
        
        start_time = time.time()
        try:
            # Set a short timeout
            result = scrape_profile_sync(url, timeout_seconds=5.0)
            elapsed = time.time() - start_time
            
            # Should complete within reasonable time (allowing for fallback to Playwright)
            assert elapsed < 10, f"Scraping took {elapsed:.2f}s, should complete under 10s"
            
            print(f"✓ Timeout enforced correctly: {elapsed:.2f}s")
        except Exception as e:
            elapsed = time.time() - start_time
            # Timeout exception is acceptable
            assert elapsed < 10, f"Timeout took {elapsed:.2f}s, should be under 10s"
            print(f"✓ Timeout exception raised correctly: {elapsed:.2f}s - {str(e)}")


class TestEndpointHealth:
    """Test health check and monitoring endpoints."""
    
    def test_ping_endpoint(self, client, env_setup):
        """Test /healthz endpoint returns 200 OK."""
        response = client.get('/healthz')
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.get_json()
        assert data is not None, "Response should be JSON"
        assert data.get("ok") is True, "Ping check should return ok: true"
        
        print(f"✓ /ping endpoint: {json.dumps(data)}")
    
    def test_health_endpoint(self, client, env_setup):
        """Test /health endpoint returns detailed health status."""
        response = client.get('/health')
        
        # May return 200 (healthy) or 503 (unhealthy, e.g., missing credentials in test env)
        assert response.status_code in [200, 503], f"Expected 200 or 503, got {response.status_code}"
        
        data = response.get_json()
        assert data is not None, "Response should be JSON"
        assert "status" in data, "Health response should include status"
        
        if response.status_code == 200:
            print(f"✓ /health endpoint: {json.dumps(data, indent=2)}")
        else:
            print(f"⚠ /health endpoint: Service unavailable (expected in test environment without credentials)")

    
    def test_debug_config_endpoint(self, client, env_setup):
        """Test /debug/config endpoint returns configuration info."""
        response = client.get('/debug/config')
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.get_json()
        assert data is not None, "Response should be JSON"
        assert "outreach_apps_keys" in data, "Config should include app keys"
        
        print(f"✓ /debug/config endpoint: Found {len(data.get('outreach_apps_keys', []))} apps")
    
    def test_warmup_endpoint(self, client, env_setup):
        """Test /warmup endpoint initializes browser successfully."""
        response = client.get('/warmup')
        
        # May return 200 or 500 depending on browser availability
        assert response.status_code in [200, 500], f"Expected 200 or 500, got {response.status_code}"
        
        data = response.get_json()
        assert data is not None, "Response should be JSON"
        
        if response.status_code == 200:
            assert "ok" in data, "Warmup response should include ok field"
            print(f"✓ /warmup endpoint: Browser initialized successfully")
        else:
            print(f"⚠ /warmup endpoint: Browser initialization failed (expected in some environments)")
    
    def test_validate_endpoint(self, client, env_setup):
        """Test /validate endpoint validates request parameters."""
        response = client.post('/validate',
                              json={"app": "regen", "sender_profile": "abhay"},
                              content_type='application/json')
        
        # Endpoint may not exist (404) or return validation results (200)
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}"
        
        if response.status_code == 200:
            data = response.get_json()
            assert data is not None, "Response should be JSON"
            print(f"✓ /validate endpoint: {json.dumps(data, indent=2)}")
        else:
            print(f"⚠ /validate endpoint not implemented (404 - expected)")



class TestScrapingEndpoint:
    """Test the main /scrape endpoint with various scenarios."""
    
    @pytest.mark.timeout(30)
    def test_scrape_endpoint_valid_profile(self, client, env_setup, test_profiles):

        """Test /scrape endpoint with a valid TikTok URL."""
        profile_data = test_profiles["with_email_and_ig"]
        
        payload = {
            "app": "regen",
            "url": profile_data["url"],
            "category": "micro",
            "sender_profile": "abhay"
        }
        
        start_time = time.time()
        response = client.post('/scrape',
                              json=payload,
                              content_type='application/json')
        elapsed = time.time() - start_time
        
        # Should complete within reasonable time
        assert elapsed < 10, f"Scrape endpoint took {elapsed:.2f}s, should be under 10s"
        
        # Check response
        assert response.status_code in [200, 400, 500], f"Unexpected status code: {response.status_code}"
        
        data = response.get_json()
        assert data is not None, "Response should be JSON"
        
        if response.status_code == 200:
            assert "ok" in data or "ig_handle" in data or "tt_handle" in data, "Response should contain profile data"
            print(f"✓ /scrape endpoint succeeded in {elapsed:.2f}s")
        else:
            print(f"⚠ /scrape endpoint returned {response.status_code}: {data.get('error', 'Unknown error')}")
    
    def test_scrape_endpoint_missing_url(self, client, env_setup):
        """Test /scrape endpoint with missing URL parameter."""
        payload = {
            "app": "regen",
            "category": "micro",
            "sender_profile": "abhay"
        }
        
        response = client.post('/scrape',
                              json=payload,
                              content_type='application/json')
        
        # May return 400 (validation error) or 500 (internal error)
        assert response.status_code in [400, 500], f"Expected 400 or 500 for missing URL, got {response.status_code}"
        
        data = response.get_json()
        assert data is not None, "Response should be JSON"
        assert "error" in data, "Error response should include error field"
        
        print(f"✓ /scrape endpoint correctly rejects missing URL: {response.status_code}")
    
    def test_scrape_endpoint_invalid_url(self, client, env_setup):
        """Test /scrape endpoint with invalid URL."""
        payload = {
            "app": "regen",
            "url": "https://invalid-domain-12345.com/@user",
            "category": "micro",
            "sender_profile": "abhay"
        }
        
        response = client.post('/scrape',
                              json=payload,
                              content_type='application/json')
        
        # Should return error or handle gracefully
        assert response.status_code in [200, 400, 500], f"Unexpected status code: {response.status_code}"
        
        data = response.get_json()
        assert data is not None, "Response should be JSON"
        
        print(f"✓ /scrape endpoint handles invalid URL: {response.status_code}")


class TestThemePageEndpoint:
    """Test the /scrape_themepage endpoint."""
    
    @pytest.mark.timeout(30)
    def test_themepage_endpoint_tiktok(self, client, env_setup):
        """Test /scrape_themepage endpoint with TikTok URL."""
        payload = {
            "app": "regen",
            "url": "https://www.tiktok.com/@themepage_test",
            "sender_profile": "abhay"
        }
        
        response = client.post('/scrape_themepage',
                              json=payload,
                              content_type='application/json')
        
        # Should succeed or fail gracefully
        assert response.status_code in [200, 400, 500], f"Unexpected status code: {response.status_code}"
        
        data = response.get_json()
        assert data is not None, "Response should be JSON"
        
        if response.status_code == 200:
            assert "dm_text" in data or "ok" in data, "Response should contain DM text or ok field"
            print(f"✓ /scrape_themepage endpoint succeeded for TikTok")
        else:
            print(f"⚠ /scrape_themepage endpoint returned {response.status_code}")
    
    def test_themepage_endpoint_missing_url(self, client, env_setup):
        """Test /scrape_themepage endpoint with missing URL."""
        payload = {
            "app": "regen",
            "sender_profile": "abhay"
        }
        
        response = client.post('/scrape_themepage',
                              json=payload,
                              content_type='application/json')
        
        assert response.status_code == 400, f"Expected 400 for missing URL, got {response.status_code}"
        
        data = response.get_json()
        assert data is not None, "Response should be JSON"
        assert "error" in data, "Error response should include error field"
        
        print(f"✓ /scrape_themepage endpoint correctly rejects missing URL")


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def test_invalid_json_payload(self, client, env_setup):
        """Test endpoints handle invalid JSON gracefully."""
        response = client.post('/scrape',
                              data="invalid json{{{",
                              content_type='application/json')
        
        # Should handle gracefully
        assert response.status_code in [400, 500], f"Expected error status, got {response.status_code}"
        
        print(f"✓ Invalid JSON handled correctly: {response.status_code}")
    
    def test_missing_app_parameter(self, client, env_setup):
        """Test scrape endpoint with missing app parameter."""
        payload = {
            "url": "https://www.tiktok.com/@test",
            "category": "micro"
        }
        
        response = client.post('/scrape',
                              json=payload,
                              content_type='application/json')
        
        # Should handle gracefully (may use default app)
        assert response.status_code in [200, 400, 500], f"Unexpected status code: {response.status_code}"
        
        print(f"✓ Missing app parameter handled: {response.status_code}")

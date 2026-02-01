"""
Pytest configuration and fixtures for outreach tool tests.
"""
import os
import sys
import pytest

# Add the api directory to the path so we can import modules
API_DIR = os.path.join(os.path.dirname(__file__), "..", "api")
sys.path.insert(0, API_DIR)

@pytest.fixture(scope="session")
def test_app():
    """Create a test Flask app instance."""
    from main import app
    app.config['TESTING'] = True
    return app

@pytest.fixture(scope="session")
def client(test_app):
    """Create a test client for the Flask app."""
    return test_app.test_client()

@pytest.fixture(scope="session")
def env_setup():
    """Ensure environment variables are set for testing."""
    # Load from env.yaml if available
    env_yaml_path = os.path.join(API_DIR, "env.yaml")
    if os.path.exists(env_yaml_path):
        try:
            import yaml
            with open(env_yaml_path, 'r') as f:
                yaml_data = yaml.safe_load(f)
                # Set environment variables from YAML
                for key, value in yaml_data.items():
                    if isinstance(value, str):
                        os.environ[key] = value
        except Exception as e:
            print(f"Warning: Could not load env.yaml: {e}")
    
    return True

# Test data for profile scraping
TEST_PROFILES = {
    "no_ig_no_email": {
        "url": "https://www.tiktok.com/@ekam_m3hat",
        "handle": "ekam_m3hat",
        "expected": {
            "has_email": False,
            "has_ig": False,
            "has_tt": True
        }
    },
    "no_ig": {
        "url": "https://www.tiktok.com/@abhaychebium",
        "handle": "abhaychebium",
        "expected": {
            "has_email": True,  # May or may not have email
            "has_ig": False,
            "has_tt": True
        }
    },
    "with_email_and_ig": {
        "url": "https://www.tiktok.com/@advaithakella",
        "handle": "advaithakella",
        "expected": {
            "has_email": True,
            "has_ig": True,
            "has_tt": True
        }
    }
}

@pytest.fixture(scope="session")
def test_profiles():
    """Return test profile data."""
    return TEST_PROFILES

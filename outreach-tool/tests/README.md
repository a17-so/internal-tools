# Outreach Tool Test Suite

Comprehensive test suite for the outreach tool API. Tests cover profile scraping, endpoint health checks, and integration scenarios.

## Quick Start

### Run All Tests

```bash
cd /Users/abhay/Documents/internal-tools/outreach-tool
./tests/run_tests.sh
```

### Run Specific Test Classes

```bash
# Run only profile scraping tests
pytest tests/test_outreach_tool.py::TestProfileScraping -v

# Run only endpoint health tests
pytest tests/test_outreach_tool.py::TestEndpointHealth -v

# Run only integration tests
pytest tests/test_outreach_tool.py::TestScrapingEndpoint -v
```

### Run Specific Tests

```bash
# Test specific profile
pytest tests/test_outreach_tool.py::TestProfileScraping::test_scrape_profile_with_email_and_ig -v

# Test health endpoint
pytest tests/test_outreach_tool.py::TestEndpointHealth::test_health_endpoint -v
```

## Test Coverage

### Profile Scraping Tests (`TestProfileScraping`)

Tests scraping functionality with real TikTok profiles:

- **test_scrape_profile_no_ig_no_email**: Tests @ekam_m3hat (no IG, no email)
- **test_scrape_profile_no_ig**: Tests @abhaychebium (no IG)
- **test_scrape_profile_with_email_and_ig**: Tests @advaithakella (has email and IG)
- **test_scrape_timeout_enforcement**: Verifies timeout handling

All scraping tests enforce a 5-second timeout.

### Endpoint Health Tests (`TestEndpointHealth`)

Tests monitoring and health check endpoints:

- **test_healthz_endpoint**: Tests `/healthz` basic health check
- **test_health_endpoint**: Tests `/health` detailed health status
- **test_debug_config_endpoint**: Tests `/debug/config` configuration info
- **test_warmup_endpoint**: Tests `/warmup` browser initialization
- **test_validate_endpoint**: Tests `/validate` request validation

### Integration Tests (`TestScrapingEndpoint`)

Tests the main scraping endpoint with various scenarios:

- **test_scrape_endpoint_valid_profile**: Tests successful scraping
- **test_scrape_endpoint_missing_url**: Tests error handling for missing URL
- **test_scrape_endpoint_invalid_url**: Tests error handling for invalid URL

### Theme Page Tests (`TestThemePageEndpoint`)

Tests the theme page endpoint:

- **test_themepage_endpoint_tiktok**: Tests theme page scraping for TikTok
- **test_themepage_endpoint_missing_url**: Tests error handling

### Error Handling Tests (`TestErrorHandling`)

Tests edge cases and error scenarios:

- **test_invalid_json_payload**: Tests handling of malformed JSON
- **test_missing_app_parameter**: Tests handling of missing app parameter

## Test Configuration

Tests are configured via `tests/conftest.py` which provides:

- **test_app**: Flask app instance for testing
- **client**: Test client for making requests
- **env_setup**: Environment variable configuration
- **test_profiles**: Test profile data for the 3 specified TikTok profiles

## Deployment Integration

The test suite is integrated into the deployment workflow via `deploy.sh`:

1. Tests run automatically before deployment
2. Deployment is **blocked** if any tests fail
3. User sees test results before proceeding
4. Only successful test runs allow deployment to continue

## Requirements

Test dependencies are included in `requirements.txt`:

- `pytest==8.0.0` - Test framework
- `pytest-timeout==2.2.0` - Timeout enforcement
- `requests==2.31.0` - HTTP client for API tests

## Environment Setup

Tests use the same environment configuration as the main application:

- Loads from `api/env.yaml` if available
- Uses environment variables for credentials
- Requires Google service account credentials for full integration tests

## Troubleshooting

### Tests Timeout

If scraping tests timeout:
- Check network connectivity
- Verify TikTok profiles are still accessible
- Increase timeout in test if needed (currently 5 seconds)

### Browser Initialization Fails

If `/warmup` endpoint tests fail:
- Ensure Playwright is installed: `python3 -m playwright install chromium`
- Check that Chromium can launch in your environment
- This is expected to fail in some CI/CD environments

### Import Errors

If tests fail with import errors:
- Ensure you're running from the project root
- Install dependencies: `pip3 install -r requirements.txt`
- Check that `api/` directory is in Python path

## CI/CD Integration

To integrate with CI/CD pipelines:

```bash
# Run tests and exit with appropriate code
./tests/run_tests.sh

# Or use pytest directly
pytest tests/ -v --tb=short
```

Exit codes:
- `0` - All tests passed
- `1` - One or more tests failed

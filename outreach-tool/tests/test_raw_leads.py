
import pytest
from unittest.mock import MagicMock, patch
from api import main

@pytest.fixture
def client():
    main.app.config['TESTING'] = True
    with main.app.test_client() as client:
        yield client

@patch('api.main._append_url_to_raw_leads_column')
@patch('api.main._check_creator_exists_across_all_sheets')
@patch('api.main._get_app_config')
@patch('api.main._resolve_sender_profile')
def test_raw_lead_uses_correct_sender_name(mock_resolve, mock_get_config, mock_check_exists, mock_append, client):
    """
    Test that the raw leads endpoint uses the 'from_name' from the resolved profile configuration,
    not just the capitalized sender profile key.
    """
    # Setup Mocks
    mock_get_config.return_value = {
        "app_key": "regen",
        "sheets_spreadsheet_id": "test_sheet_id",
        "sender_profiles": {"test_user": {"from_name": "Test User Fullname"}}
    }
    
    # Mock resolved config to include the correct from_name
    mock_resolve.return_value = {
        "app_key": "regen",
        "sheets_spreadsheet_id": "test_sheet_id",
        "gmail_sender": "test@example.com", 
        "from_name": "Test User Fullname"  # CRITICAL: This is what we expect to be used
    }
    
    mock_check_exists.return_value = {"exists": False}
    mock_append.return_value = {
        "ok": True, 
        "column_header": "Jan 01 (Test User Fullname)", 
        "row_added": 5
    }

    # Request Payload
    payload = {
        "app": "regen",
        "sender_profile": "test_user",  # Helper should convert this -> "Test User Fullname"
        "url": "https://www.instagram.com/p/12345/",
        "category": "rawlead"
    }

    # Execute Request
    response = client.post('/add_raw_leads', json=payload)

    # Assertions
    assert response.status_code == 200
    
    # Verify _append_url_to_raw_leads_column was called with the FULL NAME "Test User Fullname"
    # and NOT just "Test_user" or "Test User" inferred from the key
    mock_append.assert_called_once()
    args, kwargs = mock_append.call_args
    
    # Arg 0: spreadsheet_id
    assert args[0] == "test_sheet_id"
    # Arg 1: url
    assert args[1] == "https://www.instagram.com/p/12345"
    # Arg 2: sender_name - THIS IS THE FIX VERIFICATION
    assert args[2] == "Test User Fullname"

@patch('api.main._append_url_to_raw_leads_column')
@patch('api.main._check_creator_exists_across_all_sheets')
@patch('api.main._get_app_config')
def test_raw_lead_creator_already_exists(mock_get_config, mock_check_exists, mock_append, client):
    """Test that we reject raw leads if the creator exists in any other sheet."""
    mock_get_config.return_value = {
        "app_key": "regen",
        "sheets_spreadsheet_id": "test_sheet_id"
    }
    
    # Mock that creator exists in "Macros"
    mock_check_exists.return_value = {
        "exists": True,
        "sheet_name": "Macros",
        "row_index": 10
    }

    payload = {
        "app": "regen",
        "url": "https://www.instagram.com/some_creator",
        "category": "rawlead"
    }

    response = client.post('/add_raw_leads', json=payload)

    # Should be 409 Conflict
    assert response.status_code == 409
    data = response.get_json()
    assert "already exists" in data["error"]
    assert data["sheet_name"] == "Macros"
    
    # Should NOT have tried to append
    mock_append.assert_not_called()

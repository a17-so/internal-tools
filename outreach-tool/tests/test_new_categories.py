from unittest.mock import patch


@patch("main._append_url_to_subsheet")
@patch("main._build_email_and_dm")
@patch("main.scrape_profile_sync")
@patch("main._get_app_config")
def test_yt_creator_category_routes_to_yt_flow(
    mock_get_app_config,
    mock_scrape_profile_sync,
    mock_build_email_and_dm,
    mock_append_url_to_subsheet,
    client,
):
    mock_get_app_config.return_value = {
        "app_key": "regen",
        "sheets_spreadsheet_id": "test_sheet_id",
        "gmail_sender": "test@example.com",
        "from_name": "Tester",
    }
    mock_append_url_to_subsheet.return_value = {"ok": True, "row_added": 3, "sheet_name": "YT Creators"}
    mock_scrape_profile_sync.return_value = {
        "yt_handle": "somechannel",
        "ig": "someig",
        "tt": "somett",
        "email": "creator@example.com",
        "name": "Some Creator",
        "ytProfileUrl": "https://www.youtube.com/@somechannel",
    }
    mock_build_email_and_dm.return_value = {
        "dm_md": "DM",
        "subject": "Subject",
        "email_md": "Email body",
    }

    payload = {
        "app": "regen",
        "url": "https://www.youtube.com/@somechannel",
        "category": "YT Creator",
    }
    response = client.post("/scrape", json=payload, content_type="application/json")

    assert response.status_code == 200
    mock_append_url_to_subsheet.assert_called_once()
    args, _ = mock_append_url_to_subsheet.call_args
    assert args[1] == "YT Creators"


@patch("main._append_to_sheet")
@patch("main._build_email_and_dm")
@patch("main.scrape_profile_sync")
@patch("main._check_creator_exists_across_all_sheets")
@patch("main._get_app_config")
def test_ai_influencer_category_routes_to_ai_sheet(
    mock_get_app_config,
    mock_check_exists,
    mock_scrape_profile_sync,
    mock_build_email_and_dm,
    mock_append_to_sheet,
    client,
):
    mock_get_app_config.return_value = {
        "app_key": "regen",
        "sheets_spreadsheet_id": "test_sheet_id",
        "gmail_sender": "test@example.com",
        "instagram_account": "@tester",
        "tiktok_account": "@tester",
        "from_name": "Tester",
    }
    mock_check_exists.return_value = {"exists": False}
    mock_scrape_profile_sync.return_value = {
        "tt": "aicreator",
        "ttProfileUrl": "https://www.tiktok.com/@aicreator",
        "name": "AI Creator",
        "email": "",
    }
    mock_build_email_and_dm.return_value = {
        "dm_md": "DM",
        "subject": "Subject",
        "email_md": "Email body",
    }
    mock_append_to_sheet.return_value = {"ok": True, "row_index": 7}

    payload = {
        "app": "regen",
        "url": "https://www.tiktok.com/@aicreator",
        "category": "AI Influencer",
    }
    response = client.post("/scrape", json=payload, content_type="application/json")

    assert response.status_code == 200
    mock_append_to_sheet.assert_called_once()
    args, _ = mock_append_to_sheet.call_args
    assert args[1] == "AI Influencers"


def test_normalize_category_supports_strict_values():
    from utils import _normalize_category

    assert _normalize_category("YT Creator") == "yt_creator"
    assert _normalize_category("AI Influencer") == "ai_influencer"
    assert _normalize_category("Peptide Vendor") == "peptide_vendor"
    assert _normalize_category("Peptide Vendors") == "peptide_vendor"
    assert _normalize_category("Raw Leads") == "rawlead"
    assert _normalize_category("YouTube creators") == "youtube creators"
    assert _normalize_category("AI influencers") == "ai influencers"


@patch("main._get_app_config")
def test_scrape_rejects_non_whitelisted_category(mock_get_app_config, client):
    mock_get_app_config.return_value = {
        "app_key": "regen",
        "sheets_spreadsheet_id": "test_sheet_id",
    }

    payload = {
        "app": "regen",
        "url": "https://www.tiktok.com/@creator",
        "category": "AI influencers",
    }
    response = client.post("/scrape", json=payload, content_type="application/json")
    assert response.status_code == 400


@patch("main._get_app_config")
def test_scrape_accepts_raw_leads_category_variant(mock_get_app_config, client):
    mock_get_app_config.return_value = {
        "app_key": "regen",
        "sheets_spreadsheet_id": "test_sheet_id",
    }

    payload = {
        "app": "regen",
        "url": "https://www.tiktok.com/@creator",
        "category": "Raw Leads",
    }
    response = client.post("/scrape", json=payload, content_type="application/json")
    assert response.status_code == 400
    data = response.get_json()
    assert "creator_tier" in (data.get("error") or "")


@patch("main._append_peptide_vendor_row")
@patch("main.scrape_profile_sync")
@patch("main._get_app_config")
def test_peptide_vendor_category_routes_to_peptide_subsheet(
    mock_get_app_config,
    mock_scrape_profile_sync,
    mock_append_peptide_vendor_row,
    client,
):
    mock_get_app_config.return_value = {
        "app_key": "regen",
        "sheets_spreadsheet_id": "test_sheet_id",
        "gmail_sender": "test@example.com",
        "from_name": "Tester",
    }
    mock_scrape_profile_sync.return_value = {
        "name": "Vendor Name",
        "tt": "peptidevendor",
        "ig": "peptideig",
        "site": "https://peptidevendor.com",
        "bio": "Peptides and research compounds",
    }
    mock_append_peptide_vendor_row.return_value = {
        "ok": True,
        "row_added": 4,
        "sheet_name": "Peptide Vendors",
        "name": "Vendor Name",
        "tt_handle": "peptidevendor",
        "ig_handle": "peptideig",
        "site": "https://peptidevendor.com",
    }

    payload = {
        "app": "regen",
        "url": "https://www.tiktok.com/@peptidevendor",
        "category": "Peptide Vendor",
    }
    response = client.post("/scrape", json=payload, content_type="application/json")

    assert response.status_code == 200
    mock_scrape_profile_sync.assert_called_once()
    mock_append_peptide_vendor_row.assert_called_once()
    args, _ = mock_append_peptide_vendor_row.call_args
    assert args[1] == "Peptide Vendors"

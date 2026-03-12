import os
import sys
import re
import asyncio
from typing import Dict, Any, List, Optional
from urllib.parse import quote

from flask import Flask, request, jsonify, g
from flask_cors import CORS
import time
from datetime import datetime

# Import from new modules
from utils import _log, _normalize_category, _normalize_creator_tier, _clean_url, _markdown_to_text
from config import CATEGORY_TO_SHEET, _load_outreach_apps_config, _get_app_config, _validate_app_config, _resolve_sender_profile
from google_services import _sheets_client, _gmail_client
from sheets_operations import _hyperlink_formula, _check_creator_exists, _check_creator_exists_across_all_sheets, _check_creator_exists_in_raw_leads, _get_email_from_existing_row, _update_sheet_row, _append_url_to_raw_leads_column, _append_url_to_subsheet, _append_peptide_vendor_row, _append_to_sheet, _update_creator_contact_info
from email_operations import _send_email
from template_generation import _get_display_name, _get_templates_for_app, _build_email_and_dm

# Ensure we can import the scraper from outreach-tool/scrape_profile.py
_LOCAL_DIR = os.path.dirname(__file__)
_WORKSPACE_ROOT = os.path.abspath(os.path.join(_LOCAL_DIR, "..", ".."))
_SCRAPER_DIR = os.path.join(_WORKSPACE_ROOT, "outreach-tool")
for _p in (_LOCAL_DIR, _SCRAPER_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from scrape_profile import scrape_profile_sync
except ImportError as e:
    _log("main.import_error", error=str(e), path=sys.path)
    # Fallback for when running from root vs api dir
    try:
        sys.path.append(os.path.join(os.path.dirname(__file__)))
        from scrape_profile import scrape_profile_sync
    except ImportError:
        _log("main.critical_error", message="Could not import scrape_profile")
        raise


app = Flask(__name__)
CORS(app)  # Allow cross-origin requests from the web UI

# Load .env if present
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass


# Load multi-app configuration on startup
_OUTREACH_APPS: Dict[str, Dict[str, str]] = _load_outreach_apps_config()


# All business logic functions have been moved to separate modules:
# - utils.py: _log, _normalize_category, _clean_url, etc.
# - config.py: _load_outreach_apps_config, _get_app_config, etc.
# - google_services.py: _sheets_client, _gmail_client
# - sheets_operations.py: _check_creator_exists, _append_to_sheet, etc.
# - email_operations.py: _send_email
# - template_generation.py: _get_display_name, _build_email_and_dm, etc.



# ============================================================================
# FLASK ENDPOINTS
# ============================================================================




@app.get("/healthz")
def healthz():
    return jsonify({"ok": True})


@app.get("/debug/config")
def debug_config():
    """Debug endpoint to check configuration loading"""
    # Test specific app configs
    test_results = {}
    for app_name in _OUTREACH_APPS:
        config = _get_app_config(app_name)
        test_results[app_name] = {
            "gmail_sender": config.get("gmail_sender"),
            "sheets_spreadsheet_id": config.get("sheets_spreadsheet_id", "")[:20] + "..." if config.get("sheets_spreadsheet_id") else None,
            "delegated_user": config.get("delegated_user"),
            "link_url": config.get("link_url"),
            "tiktok_account": config.get("tiktok_account"),
            "instagram_account": config.get("instagram_account"),
            "sender_profiles": list(config.get("sender_profiles", {}).keys())
        }
    
    return jsonify({
        "outreach_apps_env_var_set": bool(os.environ.get("OUTREACH_APPS_JSON")),
        "outreach_apps_count": len(_OUTREACH_APPS),
        "outreach_apps_keys": list(_OUTREACH_APPS.keys()),
        "legacy_env_vars": {
            "SHEETS_SPREADSHEET_ID": bool(os.environ.get("SHEETS_SPREADSHEET_ID")),
            "GMAIL_SENDER": bool(os.environ.get("GMAIL_SENDER")),
            "GOOGLE_DELEGATED_USER": bool(os.environ.get("GOOGLE_DELEGATED_USER")),
            "GOOGLE_APPLICATION_CREDENTIALS": bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))
        },
        "app_configs": test_results
    })


@app.get("/health")
def health_check():
    """Comprehensive health check endpoint."""
    health = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "checks": {}
    }
    
    # Check 1: Config loaded
    try:
        if not _OUTREACH_APPS:
            health["checks"]["config"] = {
                "status": "unhealthy", 
                "error": "No apps configured",
                "detail": "OUTREACH_APPS is empty. Check env.yaml or OUTREACH_APPS_JSON environment variable."
            }
            health["status"] = "unhealthy"
        else:
            health["checks"]["config"] = {
                "status": "healthy",
                "apps": list(_OUTREACH_APPS.keys()),
                "count": len(_OUTREACH_APPS)
            }
    except Exception as e:
        health["checks"]["config"] = {"status": "unhealthy", "error": str(e)}
        health["status"] = "unhealthy"
    
    # Check 2: Sheets API
    try:
        client = _sheets_client()
        if client:
            health["checks"]["sheets_api"] = {"status": "healthy"}
        else:
            health["checks"]["sheets_api"] = {
                "status": "degraded", 
                "error": "Client not available",
                "detail": "Check GOOGLE_SERVICE_ACCOUNT_JSON secret"
            }
            if health["status"] == "healthy":
                health["status"] = "degraded"
    except Exception as e:
        health["checks"]["sheets_api"] = {"status": "degraded", "error": str(e)}
        if health["status"] == "healthy":
            health["status"] = "degraded"
    
    # Check 3: Gmail API
    try:
        client_info = _gmail_client()
        if client_info:
            health["checks"]["gmail_api"] = {"status": "healthy"}
        else:
            health["checks"]["gmail_api"] = {
                "status": "degraded", 
                "error": "Client not available",
                "detail": "Check GOOGLE_SERVICE_ACCOUNT_JSON secret and delegated_user config"
            }
            if health["status"] == "healthy":
                health["status"] = "degraded"
    except Exception as e:
        health["checks"]["gmail_api"] = {"status": "degraded", "error": str(e)}
        if health["status"] == "healthy":
            health["status"] = "degraded"
    
    # Check 4: Scraper available
    # Since we removed Playwright, this is just a static check now
    health["checks"]["scraper"] = {"status": "healthy"}
    
    status_code = 200 if health["status"] == "healthy" else (503 if health["status"] == "unhealthy" else 200)
    return jsonify(health), status_code


@app.post("/validate")
def validate_request():
    """Validate request payload without executing. Returns config that would be used.
    
    This endpoint helps debug configuration issues by showing exactly what config
    would be used for a given request, including sender profile resolution.
    
    Request body:
        {
            "app": "regen",  # Required
            "sender_profile": "abhay",  # Optional
            "category": "micro"  # Optional
        }
    
    Response:
        {
            "ok": true,
            "config": {
                "app_key": "regen",
                "gmail_sender": "abhay@a17.so",
                "delegated_user": "abhay@a17.so",
                "sheets_spreadsheet_id": "1pJbbD_o_duLKDTj_Nvtn...",
                "instagram_account": "@abhaychebium",
                "tiktok_account": "@abhaychebium",
                "from_name": "Abhay"
            },
            "sender_profile": {
                "requested": "abhay",
                "resolved": true,
                "profile": {...}
            }
        }
    """
    payload = request.get_json(silent=True) or {}
    app_key = (payload.get("app") or payload.get("app_name") or "").strip()
    sender_profile_key = (payload.get("sender_profile") or payload.get("sender") or payload.get("profile") or "").strip()
    category = payload.get("category") or ""
    
    result = {
        "ok": True,
        "request": {
            "app": app_key,
            "sender_profile": sender_profile_key or None,
            "category": category or None
        }
    }
    
    # Validate app key
    if not app_key:
        return jsonify({
            "ok": False,
            "error": "Missing required field: 'app'",
            "detail": "Provide app name in request body, e.g. {'app': 'regen'}",
            "available_apps": list(_OUTREACH_APPS.keys())
        }), 400
    
    # Get app config
    try:
        app_cfg = _get_app_config(app_key)
        
        if not app_cfg:
            return jsonify({
                "ok": False,
                "error": f"App '{app_key}' not found",
                "available_apps": list(_OUTREACH_APPS.keys()),
                "detail": "Check spelling or add app to env.yaml OUTREACH_APPS_JSON"
            }), 404
        
        # Validate app config (non-strict, just warnings)
        try:
            _validate_app_config(app_key, app_cfg, strict=False)
            result["config_validation"] = {"status": "ok"}
        except ValueError as e:
            result["config_validation"] = {"status": "warning", "message": str(e)}
        
        # Resolve sender profile if provided
        sender_profile_info = {
            "requested": sender_profile_key or None,
            "resolved": False
        }
        
        if sender_profile_key:
            try:
                resolved_cfg = _resolve_sender_profile(app_cfg, sender_profile_key, strict=True)
                app_cfg = resolved_cfg
                sender_profile_info["resolved"] = True
                sender_profile_info["profile"] = {
                    "email": resolved_cfg.get("gmail_sender"),
                    "name": resolved_cfg.get("from_name"),
                    "instagram": resolved_cfg.get("instagram_account"),
                    "tiktok": resolved_cfg.get("tiktok_account")
                }
            except ValueError as e:
                return jsonify({
                    "ok": False,
                    "error": str(e),
                    "sender_profile": sender_profile_key,
                    "available_profiles": list(app_cfg.get("sender_profiles", {}).keys())
                }), 404
        
        result["sender_profile"] = sender_profile_info
        
        # Return sanitized config
        result["config"] = {
            "app_key": app_key,
            "gmail_sender": app_cfg.get("gmail_sender"),
            "delegated_user": app_cfg.get("delegated_user"),
            "sheets_spreadsheet_id": (app_cfg.get("sheets_spreadsheet_id", "")[:20] + "..." 
                                     if app_cfg.get("sheets_spreadsheet_id") else None),
            "instagram_account": app_cfg.get("instagram_account"),
            "tiktok_account": app_cfg.get("tiktok_account"),
            "from_name": app_cfg.get("from_name"),
            "link_url": app_cfg.get("link_url")
        }
        
        # Validate category if provided
        if category:
            normalized_category = _normalize_category(category)
            sheet_name = CATEGORY_TO_SHEET.get(normalized_category)
            result["category"] = {
                "provided": category,
                "normalized": normalized_category,
                "sheet_name": sheet_name,
                "valid": sheet_name is not None
            }
        
        return jsonify(result)
        
    except Exception as e:
        _log("validate.error", error=str(e), app_key=app_key)
        return jsonify({
            "ok": False,
            "error": "Internal error during validation",
            "detail": str(e),
            "app_key": app_key,
            "sender_profile": sender_profile_key
        }), 500



def _http_request_logger_start():
    try:
        g._req_start_time = time.perf_counter()
        _log(
            "http.request",
            method=request.method,
            path=request.path,
            query=dict(request.args or {}),
            content_length=request.content_length or 0,
            remote_addr=request.headers.get("X-Forwarded-For") or request.remote_addr,
            user_agent=(request.user_agent.string if getattr(request, "user_agent", None) else ""),
        )
    except Exception:
        pass


@app.after_request
def _http_request_logger_end(response):
    try:
        start = getattr(g, "_req_start_time", None)
        dur_ms = int((time.perf_counter() - start) * 1000) if start else None
        _log(
            "http.response",
            path=request.path,
            status=response.status_code,
            duration_ms=dur_ms,
            resp_length=response.calculate_content_length() if hasattr(response, "calculate_content_length") else None,
        )
    except Exception:
        pass
    return response


@app.get("/warmup")
def warmup():
    """No-op warmup since Playwright is removed."""
    return jsonify({"ok": True, "persistent": False})


@app.post("/scrape")
@app.post("/add_raw_leads")
def scrape_endpoint():
    # Determine which app context to use
    app_key_from_query = (request.args.get("app") or request.args.get("app_name") or "").strip()

    payload = request.get_json(silent=True) or {}
    app_key = (payload.get("app") or payload.get("app_name") or app_key_from_query or "").strip()
    app_cfg = _get_app_config(app_key)
    url_raw = payload.get("tiktok_url") or payload.get("url") or ""
    # Clean the URL immediately
    url = _clean_url(url_raw)
    
    category = payload.get("category") or ""
    # Default to "rawlead" for legacy /add_raw_leads endpoint if category missing
    if not category and request.path.endswith("/add_raw_leads"):
        category = "rawlead"


    # Valid keys: "sender", "sender_profile", "profile"
    sender_profile_key = (payload.get("sender_profile") or payload.get("sender") or payload.get("profile") or "").strip().lower()
    
    # Resolve sender profile using validated function
    # Use strict=False for backward compatibility (log warnings but don't fail)
    if sender_profile_key:
        try:
            app_cfg = _resolve_sender_profile(app_cfg, sender_profile_key, strict=False)
        except ValueError as e:
            # This shouldn't happen with strict=False, but handle it anyway
            _log("scrape.sender_profile_error", error=str(e), sender_profile_key=sender_profile_key)
            return jsonify({
                "error": "Invalid sender profile",
                "detail": str(e),
                "sender_profile": sender_profile_key,
                "available_profiles": list(app_cfg.get("sender_profiles", {}).keys())
            }), 400

    _log(
        "scrape.request",
        app_key=app_cfg.get("app_key"),
        has_sheet=bool(app_cfg.get("sheets_spreadsheet_id")),
        has_sender=bool(app_cfg.get("gmail_sender")),
        has_delegated=bool(app_cfg.get("delegated_user")),
        category=category,
        sender_profile_key=sender_profile_key or None
    )
    if not url:
        return jsonify({"error": "Missing tiktok_url or url"}), 400

    # 1) First, try to extract handles from URL to check if user already exists
    spreadsheet_id = app_cfg.get("sheets_spreadsheet_id") or ""
    cat_key_normalized = _normalize_category(category)
    # Strict category whitelist for /scrape flow
    if request.path.endswith("/scrape"):
        allowed_scrape_categories = {
            "macro",
            "micro",
            "submicro",
            "ambassador",
            "themepage",
            "peptide vendor",
            "yt creator",
            "ai influencer",
        }
        category_input = (category or "").strip().lower()
        if category_input not in allowed_scrape_categories:
            return jsonify({
                "error": "Invalid category",
                "message": "Category must be one of: Macro, Micro, Submicro, Ambassador, Themepage, Peptide Vendor, YT Creator, AI Influencer",
            }), 400

    is_theme_pages = cat_key_normalized == "themepage"
    sheet_name = CATEGORY_TO_SHEET.get(cat_key_normalized)
    
    # Try to extract handles from URL without scraping
    ig_handle_from_url = ""
    tt_handle_from_url = ""
    try:
        # Extract handle from TikTok URL
        if "tiktok.com" in url.lower():
            tt_match = re.search(r'tiktok\.com/@([A-Za-z0-9_.]+)', url)
            if tt_match:
                tt_handle_from_url = tt_match.group(1)
        # Extract handle from Instagram URL
        elif "instagram.com" in url.lower():
            ig_match = re.search(r'instagram\.com/([A-Za-z0-9_.]+)', url)
            if ig_match:
                ig_handle_from_url = ig_match.group(1)
    except Exception:
        pass
    
    
    # RAW LEADS: Use column-based approach (skip scraping, just save URL)
    if cat_key_normalized == "rawlead":
        if not spreadsheet_id:
            return jsonify({"error": "No spreadsheet configured"}), 500

        raw_creator_tier = (
            payload.get("creator_tier")
            or payload.get("tier")
            or ""
        )
        creator_tier = _normalize_creator_tier(str(raw_creator_tier))
        if not creator_tier:
            return jsonify({
                "error": "Missing or invalid creator_tier",
                "message": "For raw leads, creator_tier is required: Macro, Micro, Submicro, Ambassador, Themepage, YT Creator, or AI Influencer",
            }), 400
        
        # IMPORTANT: Check if creator exists in ANY sheet (Macros, Micros, Ambassadors, Theme Pages, Raw Leads)
        # If they exist anywhere, reject the raw lead
        if ig_handle_from_url or tt_handle_from_url:
            existing_data = _check_creator_exists_across_all_sheets(
                spreadsheet_id,
                ig_handle_from_url,
                tt_handle_from_url,
                delegated_user=app_cfg.get("delegated_user") or app_cfg.get("gmail_sender") or None,
            )
            
            if existing_data.get("exists", False):
                _log(
                    "rawlead.duplicate_rejected_across_sheets",
                    ig=ig_handle_from_url,
                    tt=tt_handle_from_url,
                    found_in_sheet=existing_data.get("sheet_name"),
                    row_index=existing_data.get("row_index")
                )
                return jsonify({
                    "error": "Creator already exists",
                    "message": f"This creator already exists in '{existing_data.get('sheet_name')}' sheet",
                    "ig_handle": ig_handle_from_url,
                    "tt_handle": tt_handle_from_url,
                    "sheet_name": existing_data.get("sheet_name"),
                    "row_index": existing_data.get("row_index"),
                    "status": existing_data.get("status")
                }), 409  # 409 Conflict
        
        # Get sender name from sender_profile or default to "Unknown"
        sender_name = app_cfg.get("from_name") or (sender_profile_key.capitalize() if sender_profile_key else "Unknown")
        
        # Append row-based raw lead record
        _log("rawlead.row_append", url=url, sender=sender_name, creator_tier=creator_tier)
        result = _append_url_to_raw_leads_column(
            spreadsheet_id,
            url,
            sender_name,
            creator_tier,
            delegated_user=app_cfg.get("delegated_user") or app_cfg.get("gmail_sender") or None
        )
        
        if not result.get("ok"):
            # Duplicate URL in same column or error
            return jsonify({
                "error": result.get("error", "Failed to add raw lead"),
                "message": result.get("message", ""),
                "column_header": result.get("column_header"),
                "duplicate_row": result.get("duplicate_row")
            }), 409 if result.get("error") == "Duplicate URL" else 500
        
        # Success - return simple response
        _log("rawlead.success", column=result.get("column_header"), row=result.get("row_added"))
        return jsonify({
            "ok": True,
            "message": "Raw lead added successfully",
            "row_added": result.get("row_added"),
            "creator_tier": result.get("stored_tier"),
            "column_header": result.get("column_header"),
            "tier_column_header": result.get("tier_column_header"),
            "url": url
        })

    # PEPTIDE VENDORS: scrape TikTok profile and fill Name/TikTok/Instagram/Site columns.
    if cat_key_normalized == "peptide_vendor":
        if not spreadsheet_id:
            return jsonify({"error": "No spreadsheet configured"}), 500

        if "tiktok.com" not in url.lower():
            return jsonify({
                "error": "Invalid URL for Peptide Vendor",
                "message": "Peptide Vendor flow currently supports TikTok profile URLs only.",
            }), 400

        peptide_sheet_name = sheet_name or CATEGORY_TO_SHEET.get("peptide_vendor") or "Peptide Vendors"

        profile = {}
        try:
            profile = scrape_profile_sync(url, timeout_seconds=30.0)
        except Exception as e:
            _log("peptide_vendor.scrape_error", error=str(e))

        tt_handle = (profile.get("tt") or tt_handle_from_url or "").strip().lstrip("@")
        ig_handle = (profile.get("ig") or "").strip().lstrip("@")
        site = (profile.get("site") or "").strip()
        tiktok_bio = (profile.get("bio") or "").strip()
        name = (profile.get("name") or "").strip()
        if not name:
            name = tt_handle or "Unknown"

        _log("peptide_vendor.append", url=url, tt_handle=tt_handle, has_ig=bool(ig_handle), has_site=bool(site))
        result = _append_peptide_vendor_row(
            spreadsheet_id,
            peptide_sheet_name,
            name,
            tt_handle,
            ig_handle,
            site,
            delegated_user=app_cfg.get("delegated_user") or app_cfg.get("gmail_sender") or None,
        )

        if not result.get("ok"):
            return jsonify({
                "error": result.get("error", "Failed to add peptide vendor lead"),
                "message": result.get("message", ""),
            }), 500

        _log("peptide_vendor.success", row=result.get("row_added"))
        return jsonify({
            "ok": True,
            "message": "Peptide vendor lead added successfully",
            "sheet_name": result.get("sheet_name") or peptide_sheet_name,
            "row_added": result.get("row_added"),
            "name": result.get("name"),
            "tt_handle": result.get("tt_handle"),
            "ig_handle": result.get("ig_handle") or None,
            "site": result.get("site") or None,
            "tiktok_bio": tiktok_bio or None,
            "url": url,
        })

    # YT CREATORS: Scrape YouTube channel for IG/TT/email via SearchAPI, generate
    # DM + email scripts, log to "YT Creators" sheet, and return outreach scripts.
    if cat_key_normalized == "yt_creator":
        if not spreadsheet_id:
            return jsonify({"error": "No spreadsheet configured"}), 500

        sender_name = app_cfg.get("from_name") or (sender_profile_key.capitalize() if sender_profile_key else "Unknown")
        yt_sheet_name = sheet_name or CATEGORY_TO_SHEET.get("yt_creator") or "YT Creators"

        # 1) Log the raw URL to the YT Creators subsheet first
        _log("yt_creator.append", url=url, sender=sender_name)
        result = _append_url_to_subsheet(
            spreadsheet_id,
            yt_sheet_name,
            url,
            sender_name,
            delegated_user=app_cfg.get("delegated_user") or app_cfg.get("gmail_sender") or None,
        )

        if not result.get("ok"):
            return jsonify({
                "error": result.get("error", "Failed to add YT Creator lead"),
                "message": result.get("message", ""),
                "duplicate_row": result.get("duplicate_row"),
            }), 409 if result.get("error") == "Duplicate URL" else 500

        _log("yt_creator.logged", row=result.get("row_added"))

        # 2) Scrape the YouTube channel for contact info
        yt_profile = {}
        yt_scrape_error = None
        try:
            yt_profile = scrape_profile_sync(url, timeout_seconds=30.0)
        except Exception as e:
            yt_scrape_error = str(e)
            _log("yt_creator.scrape_error", error=yt_scrape_error)

        # Build a profile dict compatible with template rendering
        yt_handle = yt_profile.get("yt_handle") or ""
        ig_handle_yt = yt_profile.get("ig") or ""
        tt_handle_yt = yt_profile.get("tt") or ""
        email_yt = yt_profile.get("email") or ""
        name_yt = yt_profile.get("name") or yt_handle or "there"

        profile_for_template = {
            "ig": ig_handle_yt,
            "tt": tt_handle_yt,
            "name": name_yt,
            "email": email_yt,
            "igProfileUrl": f"https://www.instagram.com/{ig_handle_yt}" if ig_handle_yt else "",
            "ttProfileUrl": f"https://www.tiktok.com/@{tt_handle_yt}" if tt_handle_yt else "",
            "ytProfileUrl": yt_profile.get("ytProfileUrl") or url,
            "igAvgViews": 0,
            "ttAvgViews": 0,
        }

        # 3) Build outreach scripts using yt_creator templates
        comms = _build_email_and_dm(
            "yt_creator",
            profile_for_template,
            link_url=app_cfg.get("link_url"),
            app_key=app_cfg.get("app_key"),
            is_followup=False,
            followup_number=1,
            app_config=app_cfg,
        )

        dm_text = comms.get("dm_md") or ""
        plain_text_yt = ""
        try:
            plain_text_yt = _markdown_to_text(comms.get("email_md") or "") or ""
        except Exception:
            plain_text_yt = comms.get("email_md") or ""

        # Prepare mailto URL if email found
        mailto_yt = None
        if email_yt:
            from urllib.parse import quote as _quote
            subj_enc = _quote(comms.get("subject") or "")
            body_enc = _quote(plain_text_yt)
            mailto_yt = f"mailto:{email_yt}?subject={subj_enc}&body={body_enc}"

        _log("yt_creator.success", row=result.get("row_added"),
             has_ig=bool(ig_handle_yt), has_tt=bool(tt_handle_yt), has_email=bool(email_yt))
        return jsonify({
            "ok": True,
            "message": "YT Creator lead added successfully",
            "sheet_name": result.get("sheet_name") or yt_sheet_name,
            "row_added": result.get("row_added"),
            "url": url,
            # Contact info scraped from YouTube channel
            "yt_handle": yt_handle or None,
            "ig_handle": ig_handle_yt or None,
            "tt_handle": tt_handle_yt or None,
            "email_to": email_yt or None,
            # Outreach scripts
            "dm_text": dm_text,
            "email_subject": comms.get("subject"),
            "email_body_text": plain_text_yt,
            "mailto_url": mailto_yt,
            "scrape_error": yt_scrape_error or None,
        })

    # AI INFLUENCERS: Run full scrape/outreach pipeline (same as macro/micro/submicro)
    # but using the 'ai_influencer' template key. The URL is a TikTok or IG link.
    if cat_key_normalized == "ai_influencer":
        # Fall through to the standard scrape/outreach pipeline below
        # (cat_key_normalized is already set; sheet_name will be "AI Influencers")
        pass


    # OTHER CATEGORIES: Use existing row-based approach with scraping
    existing_data = {"exists": False}

    if spreadsheet_id and (ig_handle_from_url or tt_handle_from_url):
        # Check across all sheets
        existing_data = _check_creator_exists_across_all_sheets(
            spreadsheet_id,
            ig_handle_from_url,
            tt_handle_from_url,
            delegated_user=app_cfg.get("delegated_user") or app_cfg.get("gmail_sender") or None,
        )

        if existing_data.get("exists", False):
            _log(
                "scrape.already_contacted",
                ig=ig_handle_from_url,
                tt=tt_handle_from_url,
                found_in_sheet=existing_data.get("sheet_name"),
                row_index=existing_data.get("row_index"),
                status=existing_data.get("status"),
            )
            return jsonify({
                "error": "Creator already contacted",
                "message": f"This creator has already been reached out to (found in '{existing_data.get('sheet_name')}' sheet)",
                "ig_handle": ig_handle_from_url,
                "tt_handle": tt_handle_from_url,
                "sheet_name": existing_data.get("sheet_name"),
                "row_index": existing_data.get("row_index"),
                "status": existing_data.get("status"),
            }), 409

    
    # 2) Scrape the profile
    profile = {}
    try:
        t_scrape = time.perf_counter()
        if scrape_profile_sync is not None:
            profile = scrape_profile_sync(url, timeout_seconds=45.0)
        else:
            raise Exception("Scraper not available")
        _log("scrape.done", duration_ms=int((time.perf_counter()-t_scrape)*1000))
    except Exception as e:
        _log("scrape.error", error=str(e))
        return jsonify({"error": f"scrape failed: {e}"}), 500

    # 3) Build comms (email + DM)
    comms = _build_email_and_dm(
        category,
        profile,
        link_url=app_cfg.get("link_url"),
        app_key=app_cfg.get("app_key"),
        is_followup=False,
        followup_number=1,
        app_config=app_cfg,
    )
    _log(
        "scrape.comms_built",
        subject=comms.get("subject"),
        dm_len=len(comms.get("dm_md") or ""),
        has_email=bool(profile.get("email")),
    )

    # 4) Prepare client-side email compose data (no backend sending)
    email_send_result = {"ok": False, "error": "Skipped (no recipient)"}
    recipient_email_raw = str(profile.get("email") or "").strip()
    has_valid_recipient = bool(recipient_email_raw)
    recipient_email = recipient_email_raw if has_valid_recipient else ""
    plain_text = ""
    mailto_url: Optional[str] = None

    if has_valid_recipient and not is_theme_pages:
        # Build mailto URL and plain-text body; let device handle sending
        try:
            # Prefer plain text for mailto body
            plain_text = _markdown_to_text(comms["email_md"]) or ""
        except Exception:
            plain_text = comms.get("email_md") or ""
        # Encode subject/body for URL
        subj_enc = quote(comms.get("subject") or "")
        body_enc = quote(plain_text)
        mailto_url = f"mailto:{recipient_email}?subject={subj_enc}&body={body_enc}"
        email_send_result = {"ok": False, "error": "Skipped (compose on device)", "mailto_url": mailto_url, "to": recipient_email}
        _log("email.compose.prepared", to=recipient_email, has_mailto=bool(mailto_url))

    # 5) Write to Google Sheets or update existing row
    sheet_status = {"ok": False, "error": "No spreadsheet id configured"}
    # Always append/update a row for tracking when a spreadsheet is configured,
    # even if there is no valid recipient email (email column will be blank).
    if spreadsheet_id and sheet_name:
        name = _get_display_name(profile)
        ig_handle = profile.get("ig") or ""
        tt_handle = profile.get("tt") or ""
        email_addr = "" if is_theme_pages else (profile.get("email") or "")
        
        # Status rules:
        # - Theme Pages: leave blank (tracking DM only)
        # - If email sent OK: "Sent"
        # - If no valid recipient email: "No Email"
        # - Else (prepared compose but not sent on device): leave blank
        if is_theme_pages:
            status_val = ""
        elif email_send_result.get("ok"):
            status_val = "Sent"
        elif not has_valid_recipient:
            status_val = "No Email"
        else:
            status_val = ""

        if sheet_name == "Raw Leads":
            # For Raw Leads, use plain text URLs, no HYPERLINK formula
            ig_link = profile.get("igProfileUrl") or (f"https://www.instagram.com/{ig_handle}" if ig_handle else "")
            tt_link = profile.get("ttProfileUrl") or (f"https://www.tiktok.com/@{tt_handle}" if tt_handle else "")
        else:
            # For other sheets, use HYPERLINK formula with handle text
            ig_link = _hyperlink_formula(profile.get("igProfileUrl") or (f"https://www.instagram.com/{ig_handle}" if ig_handle else ""), f"@{ig_handle}" if ig_handle else "")
            tt_link = _hyperlink_formula(profile.get("ttProfileUrl") or (f"https://www.tiktok.com/@{tt_handle}" if tt_handle else ""), f"@{tt_handle}" if tt_handle else "")
        avg_ig_views = int(profile.get("igAvgViews") or 0)
        avg_tt_views = int(profile.get("ttAvgViews") or 0)
        
        # Get sender information from app config
        sent_from_email = app_cfg.get("gmail_sender") or ""
        sent_from_tiktok = app_cfg.get("tiktok_account") or ""
        sent_from_ig = app_cfg.get("instagram_account") or ""
        
        # Set current date for new outreaches
        initial_outreach_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Column order: Name, Instagram @, TikTok @, Email, Average Views (Instagram), Average Views (TikTok), Status, Sent from Email, Sent from IG @, Sent from TT @, Initial Outreach Date
        row = [
            name,                    # A: Name
            ig_link,                 # B: Instagram @
            tt_link,                 # C: TikTok @
            email_addr,              # D: Email
            avg_ig_views,            # E: Average Views (Instagram)
            avg_tt_views,            # F: Average Views (TikTok)
            status_val,              # G: Status
            sent_from_email,         # H: Sent from Email
            sent_from_ig,            # I: Sent from IG @
            sent_from_tiktok,        # J: Sent from TT @
            initial_outreach_date,   # K: Initial Outreach Date
        ]
        
        # Append new row
        _log("sheets.append.row_preview", sheet=sheet_name, row_sample=row[:3], avg_ig_views=avg_ig_views, avg_tt_views=avg_tt_views)
        sheet_status = _append_to_sheet(
            spreadsheet_id,
            sheet_name,
            row,
            delegated_user=app_cfg.get("delegated_user") or app_cfg.get("gmail_sender") or None,
        )
        _log("sheets.append.result", ok=sheet_status.get("ok"), error=sheet_status.get("error"), sheet_name=sheet_name)
    else:
        _log("sheets.append.skipped_no_spreadsheet")

    # Response for Shortcuts
    # Build minimal DM response
    # Prepare response for Shortcuts / client
    handle_raw = profile.get("ig")
    normalized_handle = (handle_raw or "").strip().lstrip("@")
    ig_handle = normalized_handle.lower() if normalized_handle else None
    dm_text = comms.get("dm_md") or ""
    ig_app_url = None
    if ig_handle and not is_theme_pages:
        ig_app_url = comms.get("ig_app_url") or f"instagram://user?username={ig_handle}"

    # Minimal response by default; optional extras via include_extras flag
    include_extras_val = (request.args.get("include_extras") if request else None) or (payload.get("include_extras") if isinstance(payload, dict) else None)
    include_extras = str(include_extras_val).strip().lower() in {"1", "true", "yes", "y"}

    # Always prepare email subject and body, even if no email found
    # This allows manual email entry in Shortcuts to work correctly
    if not plain_text:
        try:
            plain_text = _markdown_to_text(comms["email_md"]) or ""
        except Exception:
            plain_text = comms.get("email_md") or ""
    
    # tt_handle for the frontend (used as lookup key for sheet updates)
    tt_handle_resp = (profile.get("tt") or "").strip().lstrip("@").lower() or None

    resp = {
        "ig_handle": ig_handle,
        "tt_handle": tt_handle_resp,
        "dm_text": dm_text,
        "email_to": (recipient_email if (has_valid_recipient and not is_theme_pages) else None),
        "email_subject": comms.get("subject"),
        "email_body_text": plain_text,  # Always include body text, even if no email found
        "sent_from_email": app_cfg.get("gmail_sender"),
        "sent_from_tiktok": app_cfg.get("tiktok_account"),
        "sent_from_ig": app_cfg.get("instagram_account"),
    }

    if include_extras:
        resp.update({
            "ig_app_url": ig_app_url,
            "dmScript": dm_text,
            "igLink": ig_app_url or "IG not there",
            "mailto_url": mailto_url,
            "email_from_hint": (app_cfg.get("gmail_sender") or app_cfg.get("delegated_user") or None),
            "dm": {
                "ig_handle": ig_handle,
                "text": dm_text,
            },
        })

    # Console log a preview and the full response for debugging
    try:
        _log(
            "scrape.response_preview",
            ig_handle=ig_handle,
            dm_len=len(dm_text),
            has_ig_url=bool(ig_app_url),
        )
        print(json.dumps({"api_response": resp}, ensure_ascii=False))
    except Exception:
        pass

    return jsonify(resp)


@app.post("/scrape_themepage")
def scrape_themepage_endpoint():
    """
    Dedicated endpoint for theme page outreach.
    
    Theme pages are handled differently:
    - No scraping (most don't have IG/Email)
    - Extract handle from URL directly
    - Generate DM script only
    - Add to spreadsheet for tracking
    
    Request body:
        {
            "app": "regen",
            "url": "https://tiktok.com/@themepage_handle",
            "sender_profile": "abhay"
        }
    
    Response:
        {
            "ok": true,
            "ig_handle": "themepage_handle",
            "dm_text": "personalized DM script...",
            "ig_app_url": "instagram://user?username=themepage_handle",
            "added_to_sheet": true
        }
    """
    payload = request.get_json(silent=True) or {}
    app_key = (payload.get("app") or payload.get("app_name") or "").strip()
    url_raw = payload.get("url") or payload.get("tiktok_url") or ""
    url = _clean_url(url_raw)
    sender_profile_key = (payload.get("sender_profile") or payload.get("sender") or payload.get("profile") or "").strip().lower()
    
    # Get app config
    app_cfg = _get_app_config(app_key)
    
    # Resolve sender profile
    if sender_profile_key:
        try:
            app_cfg = _resolve_sender_profile(app_cfg, sender_profile_key, strict=False)
        except ValueError as e:
            _log("scrape_themepage.sender_profile_error", error=str(e), sender_profile_key=sender_profile_key)
            return jsonify({
                "error": "Invalid sender profile",
                "detail": str(e),
                "sender_profile": sender_profile_key,
                "available_profiles": list(app_cfg.get("sender_profiles", {}).keys())
            }), 400
    
    _log(
        "scrape_themepage.request",
        app_key=app_cfg.get("app_key"),
        has_sheet=bool(app_cfg.get("sheets_spreadsheet_id")),
        sender_profile_key=sender_profile_key or None
    )
    
    if not url:
        return jsonify({"error": "Missing url or tiktok_url"}), 400
    
    # Extract handle from URL without scraping
    ig_handle = ""
    tt_handle = ""
    platform = ""
    
    try:
        if "tiktok.com" in url.lower():
            tt_match = re.search(r'tiktok\.com/@([A-Za-z0-9_.]+)', url)
            if tt_match:
                tt_handle = tt_match.group(1)
                platform = "tiktok"
        elif "instagram.com" in url.lower():
            ig_match = re.search(r'instagram\.com/([A-Za-z0-9_.]+)', url)
            if ig_match:
                ig_handle = ig_match.group(1)
                platform = "instagram"
    except Exception as e:
        _log("scrape_themepage.handle_extraction_error", error=str(e), url=url)
        return jsonify({"error": f"Failed to extract handle from URL: {e}"}), 400
    
    if not ig_handle and not tt_handle:
        return jsonify({"error": "Could not extract handle from URL. Please provide a valid TikTok or Instagram URL."}), 400
    
    # Check if theme page already exists
    spreadsheet_id = app_cfg.get("sheets_spreadsheet_id") or ""
    existing_data = {"exists": False}

    if spreadsheet_id and (ig_handle or tt_handle):
        existing_data = _check_creator_exists_across_all_sheets(
            spreadsheet_id,
            ig_handle,
            tt_handle,
            delegated_user=app_cfg.get("delegated_user") or app_cfg.get("gmail_sender") or None,
        )

        if existing_data.get("exists", False):
            _log(
                "scrape_themepage.already_contacted",
                ig=ig_handle,
                tt=tt_handle,
                found_in_sheet=existing_data.get("sheet_name"),
                row_index=existing_data.get("row_index"),
                status=existing_data.get("status"),
            )
            return jsonify({
                "error": "Creator already contacted",
                "message": f"This creator has already been reached out to (found in '{existing_data.get('sheet_name')}' sheet)",
                "ig_handle": ig_handle,
                "tt_handle": tt_handle,
                "sheet_name": existing_data.get("sheet_name"),
                "row_index": existing_data.get("row_index"),
                "status": existing_data.get("status"),
            }), 409
    
    # Create minimal profile object (no scraping)
    profile = {
        "ig": ig_handle,
        "tt": tt_handle,
        "name": ig_handle or tt_handle or "there",
        "email": "",  # Theme pages don't have emails
        "igProfileUrl": f"https://www.instagram.com/{ig_handle}" if ig_handle else "",
        "ttProfileUrl": f"https://www.tiktok.com/@{tt_handle}" if tt_handle else "",
        "igAvgViews": 0,
        "ttAvgViews": 0,
        "platform": platform,
    }
    
    _log("scrape_themepage.profile_created", ig=ig_handle, tt=tt_handle, platform=platform)
    
    # Build DM script using theme page templates
    comms = _build_email_and_dm(
        "themepage",
        profile,
        link_url=app_cfg.get("link_url"),
        app_key=app_cfg.get("app_key"),
        is_followup=False,
        followup_number=1,
    )
    
    dm_text = comms.get("dm_md") or ""
    _log("scrape_themepage.dm_generated", dm_len=len(dm_text))
    
    # Add to spreadsheet
    sheet_status = {"ok": False, "error": "No spreadsheet configured"}
    sheet_name = "Theme Pages"  # Always use Theme Pages sheet
    
    if spreadsheet_id:
        name = _get_display_name(profile)
        
        # Create links
        ig_link = _hyperlink_formula(profile.get("igProfileUrl") or (f"https://www.instagram.com/{ig_handle}" if ig_handle else ""), f"@{ig_handle}" if ig_handle else "")
        tt_link = _hyperlink_formula(profile.get("ttProfileUrl") or (f"https://www.tiktok.com/@{tt_handle}" if tt_handle else ""), f"@{tt_handle}" if tt_handle else "")
        
        # Get sender information
        sent_from_email = app_cfg.get("gmail_sender") or ""
        sent_from_tiktok = app_cfg.get("tiktok_account") or ""
        sent_from_ig = app_cfg.get("instagram_account") or ""
        
        # Status for theme pages (leave blank)
        status_val = ""
        initial_outreach_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Column order: Name, Instagram @, TikTok @, Email (blank), Average Views (IG), Average Views (TT), Status, Sent from Email, Sent from IG @, Sent from TT @, Initial Outreach Date
        row = [
            name,                    # A: Name
            ig_link,                 # B: Instagram @
            tt_link,                 # C: TikTok @
            "",                      # D: Email (always blank for theme pages)
            0,                       # E: Average Views (Instagram)
            0,                       # F: Average Views (TikTok)
            status_val,              # G: Status
            sent_from_email,         # H: Sent from Email
            sent_from_ig,            # I: Sent from IG @
            sent_from_tiktok,        # J: Sent from TT @
            initial_outreach_date,   # K: Initial Outreach Date
        ]
        
        # Append new row
        _log("scrape_themepage.append_row", sheet=sheet_name, name=name)
        sheet_status = _append_to_sheet(
            spreadsheet_id,
            sheet_name,
            row,
            delegated_user=app_cfg.get("delegated_user") or app_cfg.get("gmail_sender") or None,
        )

        _log("scrape_themepage.sheet_result", ok=sheet_status.get("ok"), error=sheet_status.get("error"))
    
    # Prepare response
    handle_for_dm = ig_handle or tt_handle
    normalized_handle = (handle_for_dm or "").strip().lstrip("@")
    ig_app_url = None
    if ig_handle:
        ig_app_url = f"instagram://user?username={normalized_handle}"
    
    resp = {
        "ok": True,
        "ig_handle": normalized_handle.lower() if normalized_handle else None,
        "tt_handle": tt_handle or None,
        "dm_text": dm_text,
        "ig_app_url": ig_app_url,
        "added_to_sheet": sheet_status.get("ok", False),
        "platform": platform,
    }

    _log(
        "scrape_themepage.response",
        handle=normalized_handle,
        dm_len=len(dm_text),
        added_to_sheet=sheet_status.get("ok", False),
    )
    
    return jsonify(resp)


@app.patch("/update_creator_contact")
def update_creator_contact_endpoint():
    """
    Update the email and/or IG handle for an existing creator row in Google Sheets.

    This is called when the user manually enters/edits the email or IG in the
    web tool after scraping returns incomplete data.

    Request body:
        {
            "app": "regen",
            "ig_handle": "scraped_ig_handle",     # used for row lookup
            "tt_handle": "scraped_tt_handle",     # used for row lookup
            "new_email": "creator@email.com",     # optional, write to col D
            "new_ig": "new_ig_handle"             # optional, write to col B
        }

    Response:
        { "ok": true, "updated": ["email", "ig"] }
    """
    payload = request.get_json(silent=True) or {}
    app_key = (payload.get("app") or "").strip()
    ig_handle_lookup = (payload.get("ig_handle") or "").strip().lstrip("@")
    tt_handle_lookup = (payload.get("tt_handle") or "").strip().lstrip("@")
    new_email = (payload.get("new_email") or "").strip()
    new_ig = (payload.get("new_ig") or "").strip().lstrip("@")

    if not app_key:
        return jsonify({"ok": False, "error": "Missing app"}), 400
    if not new_email and not new_ig:
        return jsonify({"ok": False, "error": "Nothing to update"}), 400

    app_cfg = _get_app_config(app_key)
    spreadsheet_id = app_cfg.get("spreadsheet_id") or app_cfg.get("sheet_id")
    if not spreadsheet_id:
        return jsonify({"ok": False, "error": "No spreadsheet configured for this app"}), 400

    delegated_user = app_cfg.get("delegated_user") or app_cfg.get("gmail_sender") or None

    # Find the existing row in any sheet tab
    existing = _check_creator_exists_across_all_sheets(
        spreadsheet_id, ig_handle_lookup, tt_handle_lookup, delegated_user=delegated_user
    )

    if not existing.get("exists"):
        _log("update_creator_contact.not_found", ig=ig_handle_lookup, tt=tt_handle_lookup)
        return jsonify({"ok": False, "error": "Creator not found in sheet"}), 404

    sheet_name = existing["sheet_name"]
    row_index = existing["row_index"]
    _log("update_creator_contact.found", sheet=sheet_name, row=row_index)

    result = _update_creator_contact_info(
        spreadsheet_id,
        sheet_name,
        row_index,
        email=new_email or None,
        ig_handle=new_ig or None,
        delegated_user=delegated_user,
    )

    return jsonify(result)


# Entrypoint for local dev: `python api/main.py`
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)

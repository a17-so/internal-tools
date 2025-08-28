import os
import sys
import json
import base64
import asyncio
from typing import Dict, Any, List, Optional

from flask import Flask, request, jsonify
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Google APIs (Sheets + Gmail)
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
except Exception:
    service_account = None
    build = None

# ADC (user OAuth) fallback
try:
    import google.auth  # type: ignore
except Exception:
    google = None  # type: ignore


# Ensure we can import the scraper from outreach-tool/scrape_profile.py
_LOCAL_DIR = os.path.dirname(__file__)
_WORKSPACE_ROOT = os.path.abspath(os.path.join(_LOCAL_DIR, "..", ".."))
_SCRAPER_DIR = os.path.join(_WORKSPACE_ROOT, "outreach-tool")
for _p in (_LOCAL_DIR, _SCRAPER_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SCRAPER_IMPORT_ERROR = None
scrape_profile = None  # type: ignore
try:
    # First attempt: import by module name with sys.path including outreach-tool
    from scrape_profile import scrape_profile as _scrape_profile  # type: ignore
    scrape_profile = _scrape_profile
except Exception as import_err:
    # Fallback: load directly from file path
    try:
        import importlib.util
        candidate_paths = [
            os.path.join(_LOCAL_DIR, "scrape_profile.py"),
            os.path.join(_SCRAPER_DIR, "scrape_profile.py"),
        ]
        last_err = None
        for _scraper_path in candidate_paths:
            try:
                if not os.path.exists(_scraper_path):
                    continue
                spec = importlib.util.spec_from_file_location("scrape_profile", _scraper_path)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
                    scrape_profile = getattr(mod, "scrape_profile", None)
                    if scrape_profile is not None:
                        last_err = None
                        break
                    last_err = "scrape_profile() not found in module"
                else:
                    last_err = f"Could not create spec for {_scraper_path}"
            except Exception as _e:
                last_err = str(_e)
        if scrape_profile is None:
            SCRAPER_IMPORT_ERROR = f"{import_err}; fallback tried {candidate_paths} → {last_err}"
    except Exception as e:
        SCRAPER_IMPORT_ERROR = f"{import_err}; fallback failed: {e}"


app = Flask(__name__)

# Load .env if present
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass


CATEGORY_TO_SHEET = {
    "macro": "Macros",
    "micro": "Micros",
    "ambassador": "Ambassadors",
}


# ---- Multi-app configuration -------------------------------------------------
#
# Support multiple outreach "apps" with distinct Google Sheets and Gmail senders.
# Provide a JSON env var OUTREACH_APPS_JSON like:
# {
#   "default": {
#     "sheets_spreadsheet_id": "<sheet-id>",
#     "gmail_sender": "sender@example.com",
#     "delegated_user": "sender@example.com",
#     "link_url": "https://a17.so/brief"
#   },
#   "pretti": {
#     "sheets_spreadsheet_id": "<sheet-id>",
#     "gmail_sender": "pretti@example.com",
#     "delegated_user": "pretti@example.com",
#     "link_url": "https://pretti.app/brief"
#   }
# }
# If not provided, falls back to legacy single-app env vars.

def _load_outreach_apps_config() -> Dict[str, Dict[str, str]]:
    raw = os.environ.get("OUTREACH_APPS_JSON") or ""
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            # ensure nested dicts
            return {str(k): (v if isinstance(v, dict) else {}) for k, v in data.items()}
    except Exception:
        pass
    return {}


_OUTREACH_APPS: Dict[str, Dict[str, str]] = _load_outreach_apps_config()


def _get_app_config(app_key: Optional[str]) -> Dict[str, str]:
    key = (app_key or "").strip().lower() or "default"
    # Merge default with app-specific
    default_cfg = _OUTREACH_APPS.get("default", {})
    specific_cfg = _OUTREACH_APPS.get(key, {}) if key != "default" else {}
    merged: Dict[str, str] = {**default_cfg, **specific_cfg}

    # Legacy fallbacks when JSON config not provided
    if not merged.get("sheets_spreadsheet_id"):
        legacy_sheet = os.environ.get("SHEETS_SPREADSHEET_ID") or ""
        if legacy_sheet:
            merged["sheets_spreadsheet_id"] = legacy_sheet
    if not merged.get("gmail_sender"):
        legacy_sender = os.environ.get("GMAIL_SENDER") or ""
        if legacy_sender:
            merged["gmail_sender"] = legacy_sender
    if not merged.get("delegated_user"):
        # Either GOOGLE_DELEGATED_USER or the sender itself
        legacy_delegated = os.environ.get("GOOGLE_DELEGATED_USER") or merged.get("gmail_sender") or ""
        if legacy_delegated:
            merged["delegated_user"] = legacy_delegated
    if not merged.get("link_url"):
        merged["link_url"] = "https://a17.so/brief"

    merged["app_key"] = key
    return merged


def _normalize_category(category: str) -> str:
    if not category:
        return ""
    c = category.strip().lower()
    # handle common misspellings/variants
    if c.startswith("macro"):
        return "macro"
    if c.startswith("micro"):
        return "micro"
    if c.startswith("ambas"):
        return "ambassador"
    return c


def _load_service_account_credentials(scopes: List[str], delegated_user: Optional[str] = None):
    """Load service account credentials from env.

    Accepts either:
    - GOOGLE_SERVICE_ACCOUNT_JSON (raw JSON string)
    - GOOGLE_APPLICATION_CREDENTIALS (path to json file)

    If delegated_user is provided, returns a delegated credentials object
    (requires domain-wide delegation to be configured in Google Admin).
    """
    if service_account is None:
        return None

    raw_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

    creds = None
    if raw_json:
        info = json.loads(raw_json)
        creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
    elif cred_path:
        creds = service_account.Credentials.from_service_account_file(cred_path, scopes=scopes)
    else:
        return None

    if delegated_user:
        creds = creds.with_subject(delegated_user)
    return creds


def _load_default_credentials(scopes: List[str]):
    """Load Application Default Credentials for the active user.

    Requires: `gcloud auth application-default login`.
    Returns credentials or None if unavailable.
    """
    try:
        if google is None:  # type: ignore
            return None
        creds, _ = google.auth.default(scopes=scopes)  # type: ignore[attr-defined]
        return creds
    except Exception:
        return None


def _sheets_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    creds = _load_service_account_credentials(scopes=scopes)
    if not creds:
        creds = _load_default_credentials(scopes=scopes)
    if not creds or build is None:
        return None
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _gmail_client(delegated_user_override: Optional[str] = None):
    scopes = [
        "https://www.googleapis.com/auth/gmail.send",
    ]
    delegated_user = (
        delegated_user_override
        or os.environ.get("GOOGLE_DELEGATED_USER")
        or os.environ.get("GMAIL_SENDER")
    )
    # Try service account with delegation first
    creds = _load_service_account_credentials(scopes=scopes, delegated_user=delegated_user)
    user_id = delegated_user or "me"
    # Fallback to user ADC if no SA creds configured
    if not creds:
        creds = _load_default_credentials(scopes=scopes)
        user_id = "me"
    if not creds or build is None:
        return None
    return build("gmail", "v1", credentials=creds, cache_discovery=False), user_id


def _hyperlink_formula(url: str, label: str) -> str:
    if not url:
        return label or ""
    safe_url = url.replace('"', "\"")
    safe_label = (label or "").replace('"', "\"")
    return f"=HYPERLINK(\"{safe_url}\", \"{safe_label}\")"


def _get_display_name(profile: Dict[str, Any]) -> str:
    """Choose a friendly display name, avoiding generic TikTok titles."""
    # Prefer IG handle (lowercased) per requirement
    ig_handle = (profile.get("ig") or "").strip()
    if ig_handle:
        return ig_handle.lower()
    raw = (profile.get("name") or "").strip()
    if raw:
        lowered = raw.lower()
        if not (
            "tiktok - make your day" in lowered
            or lowered == "tiktok"
            or lowered.startswith("tiktok ·")
        ):
            return raw
    # Fallback to handles when name is missing or generic
    ig = (profile.get("ig") or "").strip()
    tt = (profile.get("tt") or "").strip()
    return ig or tt or "there"


def _get_templates_for_app(app_key: Optional[str]) -> Dict[str, Dict[str, str]]:
    """Dynamically load TEMPLATES dict from api/scripts/<app_key>.py.

    Falls back to generic templates from api/scripts.py if per-app not found.
    """
    key = (app_key or "").strip().lower() or "default"
    # Try app-specific module (package import)
    try:
        import importlib
        mod = importlib.import_module(f"scripts.{key}")
        t = getattr(mod, "TEMPLATES", None)
        if isinstance(t, dict):
            return t
    except Exception:
        pass

    # Try loading from file path to avoid conflicts with scripts.py module
    try:
        import importlib.util
        candidate = os.path.join(_LOCAL_DIR, "scripts", f"{key}.py")
        if os.path.exists(candidate):
            spec = importlib.util.spec_from_file_location(f"scripts_{key}", candidate)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)  # type: ignore[attr-defined]
                t = getattr(mod, "TEMPLATES", None)
                if isinstance(t, dict):
                    return t
    except Exception:
        pass
    # Fallback to generic scripts.TEMPLATES
    try:
        from scripts import TEMPLATES as GENERIC_TEMPLATES  # type: ignore
        if isinstance(GENERIC_TEMPLATES, dict):
            return GENERIC_TEMPLATES  # type: ignore
    except Exception:
        pass
    return {}


def _build_email_and_dm(category: str, profile: Dict[str, Any], personalization: str = "", link_url: Optional[str] = None, app_key: Optional[str] = None) -> Dict[str, Any]:
    name = _get_display_name(profile)
    ig_handle = profile.get("ig") or ""
    tt_handle = profile.get("tt") or ""

    # Load markdown templates
    templates_for_app = _get_templates_for_app(app_key)
    key = _normalize_category(category)
    tmpl = templates_for_app.get(key) or {}
    link_url = link_url or "https://a17.so/brief"
    link_text = "View brief"

    # Prepare Markdown strings
    email_md = tmpl.get("email_md") or (
        "Hi {name}\n\n{personalization}\n\nBest,\nAbhay\n\n*abhay@a17.so*"
    )
    dm_md = tmpl.get("dm_md") or (
        "Hey {name}! {personalization}"
    )

    personalization_clean = personalization.strip()
    email_md = email_md.format(
        name=name,
        personalization=personalization_clean,
        link_url=link_url,
        link_text=link_text,
    )
    dm_md = dm_md.format(name=name, personalization=personalization_clean)

    subject = tmpl.get("subject") or f"PAID PARTNERSHIP OPPORTUNITY - Pretti App"

    return {
        "subject": subject,
        "email_md": email_md,
        "dm_md": dm_md,
        "ig_app_url": f"instagram://user?username={ig_handle}" if ig_handle else "",
    }

    key = _normalize_category(category)
    t = templates.get(key, templates["micro"])  # default to micro

    ig_app_url = ""
    if ig_handle:
        ig_app_url = f"instagram://user?username={ig_handle}"

    return {
        "subject": t["subject"],
        "email_body": t["email_body"],
        "dm_text": t["dm"],
        "ig_app_url": ig_app_url,
    }


def _append_to_sheet(spreadsheet_id: str, sheet_name: str, row_values: List[Any]) -> Dict[str, Any]:
    service = _sheets_client()
    if not service:
        return {"ok": False, "error": "Sheets client not configured"}

    body = {"values": [row_values]}
    try:
        resp = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A:K",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body,
        ).execute()
        return {"ok": True, "result": resp}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _send_email(subject: str, body_text: str, to_email: str, from_email_override: Optional[str] = None, delegated_user_override: Optional[str] = None) -> Dict[str, Any]:
    if not to_email:
        return {"ok": False, "error": "No recipient email"}

    client_info = _gmail_client(delegated_user_override=delegated_user_override)
    if not client_info:
        return {"ok": False, "error": "Gmail client not configured"}
    gmail, user_id = client_info

    from_email = (
        from_email_override
        or os.environ.get("GMAIL_SENDER")
        or (user_id if isinstance(user_id, str) else "")
    )
    # When using ADC (user_id == "me"), From can be omitted.

    try:
        msg_lines = []
        if from_email:
            msg_lines.append(f"From: {from_email}")
        msg_lines.append(f"To: {to_email}")
        msg_lines.append(f"Subject: {subject}")
        msg_lines.append("Content-Type: text/plain; charset=utf-8")
        msg_lines.append("")
        msg_lines.append(body_text)
        msg = ("\r\n".join(msg_lines)).encode("utf-8")
        raw = base64.urlsafe_b64encode(msg).decode("utf-8")
        resp = gmail.users().messages().send(userId=user_id, body={"raw": raw}).execute()
        return {"ok": True, "result": resp}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/healthz")
def healthz():
    return jsonify({"ok": True})


@app.post("/scrape")
def scrape_endpoint():
    # Determine which app context to use
    app_key_from_query = (request.args.get("app") or request.args.get("app_name") or "").strip()
    if scrape_profile is None:
        return jsonify({
            "error": "scraper not available",
            "details": SCRAPER_IMPORT_ERROR or "unknown import error",
            "fix": "Install Playwright: pip install playwright && python -m playwright install chromium"
        }), 500

    payload = request.get_json(silent=True) or {}
    app_key = (payload.get("app") or payload.get("app_name") or app_key_from_query or "").strip()
    app_cfg = _get_app_config(app_key)
    url = payload.get("tiktok_url") or payload.get("url") or ""
    category = payload.get("category") or ""
    # New single personalization field; keep backward-compat with p1/p2
    legacy_p1 = payload.get("p1") or payload.get("personalization1") or ""
    legacy_p2 = payload.get("p2") or payload.get("personalization2") or ""
    personalization = payload.get("personalization") or "".strip()
    if not personalization:
        parts = [p for p in [legacy_p1, legacy_p2] if p]
        personalization = "\n".join(parts)

    if not url:
        return jsonify({"error": "Missing tiktok_url or url"}), 400

    # 1) Scrape
    try:
        profile = asyncio.run(scrape_profile(url))
    except Exception as e:
        return jsonify({"error": f"scrape failed: {e}"}), 500

    # 2) Build comms (email + DM)
    # Force name to be the IG handle (lowercased) if available
    ig_lower = (profile.get("ig") or "").lower()
    if ig_lower:
        profile["name"] = ig_lower
    comms = _build_email_and_dm(
        category,
        profile,
        personalization=personalization,
        link_url=app_cfg.get("link_url"),
        app_key=app_cfg.get("app_key"),
    )

    # 3) Send Email (best-effort)
    email_send_result = {"ok": False, "error": "Skipped (no recipient)"}
    recipient_email = profile.get("email")
    if recipient_email:
        # Render HTML from Markdown for email, plain text fallback
        try:
            import markdown as md
            html_body = md.markdown(comms["email_md"], extensions=["extra", "sane_lists"])
        except Exception:
            html_body = comms["email_md"].replace("\n", "<br/>")

        # Build MIME message
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(comms["email_md"], "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        email_send_result = _send_email(
            subject=comms["subject"],
            body_text=msg.as_string(),
            to_email=recipient_email,
            from_email_override=app_cfg.get("gmail_sender"),
            delegated_user_override=app_cfg.get("delegated_user"),
        )

    # 4) Write to Google Sheets after email attempt
    spreadsheet_id = app_cfg.get("sheets_spreadsheet_id") or ""
    sheet_status = {"ok": False, "error": "No spreadsheet id configured"}
    sheet_name = None
    if spreadsheet_id:
        cat_key = _normalize_category(category)
        sheet_name = CATEGORY_TO_SHEET.get(cat_key)
        if sheet_name:
            name = profile.get("name") or ""
            ig_handle = profile.get("ig") or ""
            tt_handle = profile.get("tt") or ""
            yt_handle = profile.get("yt") or ""
            ig_followers = int(profile.get("igFollowers") or 0)
            tt_followers = int(profile.get("ttFollowers") or 0)
            yt_followers = int(profile.get("ytFollowers") or 0)
            total_followers = ig_followers + tt_followers + yt_followers
            email_addr = profile.get("email") or ""
            # Only mark as Sent if email successfully sent; otherwise leave blank
            status_val = "Sent" if email_send_result.get("ok") else ""

            ig_link = _hyperlink_formula(profile.get("igProfileUrl") or (f"https://www.instagram.com/{ig_handle}" if ig_handle else ""), f"@{ig_handle}" if ig_handle else "")
            tt_link = _hyperlink_formula(profile.get("ttProfileUrl") or (f"https://www.tiktok.com/@{tt_handle}" if tt_handle else ""), f"@{tt_handle}" if tt_handle else "")
            yt_link = _hyperlink_formula("", yt_handle or "")

            row = [
                name,
                ig_link,
                tt_link,
                yt_link,
                ig_followers,
                tt_followers,
                yt_followers,
                total_followers,
                email_addr,
                status_val,
            ]
            sheet_status = _append_to_sheet(spreadsheet_id, sheet_name, row)
        else:
            sheet_status = {"ok": False, "error": f"Unknown category: {category}"}

    # Response for Shortcuts
    # Build minimal DM response
    ig_handle = (profile.get("ig") or "").lower()
    dm_text = comms.get("dm_md") or ""
    resp = {
        "dm": {
            "ig_handle": ig_handle,
            "text": dm_text,
        }
    }

    return jsonify(resp)


# Entrypoint for local dev: `python api/main.py`
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)



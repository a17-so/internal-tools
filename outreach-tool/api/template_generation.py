"""Template and script generation for the outreach tool."""

import os
import importlib
import importlib.util
from typing import Dict, Any, Optional

from utils import _log, _normalize_category
from config import _get_app_config


def _get_display_name(profile: Dict[str, Any]) -> str:
    """Choose a friendly display name, avoiding generic TikTok titles."""
    # Prefer TikTok handle (lowercased) as the creator name
    tt_handle = (profile.get("tt") or "").strip()
    if tt_handle:
        return tt_handle.lower()
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
    tt = (profile.get("tt") or "").strip()
    ig = (profile.get("ig") or "").strip()
    return tt or ig or "there"



def _get_templates_for_app(app_key: Optional[str], followup: bool = False, followup_number: int = 1, app_config: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, str]]:
    """Dynamically load templates from api/scripts/<app_key>.py using the new dynamic functions.

    Falls back to generic templates from api/scripts.py if per-app not found.
    
    Args:
        app_key: The app key (e.g., 'lifemaxx', 'pretti')
        followup: Whether to load followup templates
        followup_number: Which followup template to load (1, 2, or 3)
        app_config: Optional resolved app configuration dict (containing resolved sender profile)
    """
    key = (app_key or "").strip().lower() or "default"
    
    # Get app configuration to pass to template functions
    # Use passed config if available, otherwise fetch raw config
    if not app_config:
        app_config = _get_app_config(app_key)
    
    _log("template.lookup.start", app_key=key, followup=followup, followup_number=followup_number, app_config_keys=list(app_config.keys()))
    
    # Try app-specific module (package import)
    try:
        mod = importlib.import_module(f"scripts.{key}")
        
        # Use the new dynamic template functions
        if followup:
            if followup_number == 1:
                template_func = getattr(mod, "get_followup_templates", None)
            elif followup_number == 2:
                template_func = getattr(mod, "get_second_followup_templates", None)
            elif followup_number == 3:
                template_func = getattr(mod, "get_third_followup_templates", None)
            else:
                template_func = getattr(mod, "get_followup_templates", None)  # fallback to first followup
        else:
            template_func = getattr(mod, "get_templates", None)
        
        if template_func and callable(template_func):
            t = template_func(app_name=key, app_config=app_config)
            if isinstance(t, dict):
                _log("template.lookup.success.module", app_key=key, found_keys=list(t.keys()))
                return t
    except Exception as e:
        _log("template.lookup.error.module", app_key=key, error=str(e))
    
    # Try loading from file path to avoid conflicts with scripts.py module
    # ... (rest of function remains same but needs consistent app_config usage)
    try:
        api_dir = os.path.dirname(__file__)
        candidate = os.path.join(api_dir, "scripts", f"{key}.py")
        if os.path.exists(candidate):
            spec = importlib.util.spec_from_file_location(f"scripts_{key}", candidate)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)  # type: ignore[attr-defined]
                
                # Use the new dynamic template functions
                if followup:
                    if followup_number == 1:
                        template_func = getattr(mod, "get_followup_templates", None)
                    elif followup_number == 2:
                        template_func = getattr(mod, "get_second_followup_templates", None)
                    elif followup_number == 3:
                        template_func = getattr(mod, "get_third_followup_templates", None)
                    else:
                        template_func = getattr(mod, "get_followup_templates", None)  # fallback to first followup
                else:
                    template_func = getattr(mod, "get_templates", None)
                
                if template_func and callable(template_func):
                    t = template_func(app_name=key, app_config=app_config)
                    if isinstance(t, dict):
                        _log("template.lookup.success.file", app_key=key, found_keys=list(t.keys()))
                        return t
    except Exception as e:
        _log("template.lookup.error.file", app_key=key, error=str(e))
    
    # Fallback to generic scripts.TEMPLATES
    if not followup:
        try:
            from scripts import TEMPLATES as GENERIC_TEMPLATES  # type: ignore
            if isinstance(GENERIC_TEMPLATES, dict):
                _log("template.lookup.success.fallback", app_key=key, found_keys=list(GENERIC_TEMPLATES.keys()))
                return GENERIC_TEMPLATES  # type: ignore
        except Exception as e:
            _log("template.lookup.error.fallback", app_key=key, error=str(e))
    
    _log("template.lookup.failed", app_key=key)
    return {}


def _build_email_and_dm(category: str, profile: Dict[str, Any], link_url: Optional[str] = None, app_key: Optional[str] = None, is_followup: bool = False, followup_number: int = 1, app_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build email and DM scripts from templates.
    
    Args:
        category: Category of creator (macro, micro, submicro, ambassador, themepage)
        profile: Profile data dict with name, ig, tt handles
        link_url: Optional URL to include in templates
        app_key: App key for template lookup
        is_followup: Whether this is a followup message
        followup_number: Which followup (1, 2, or 3)
        app_config: Optional resolved app configuration dict
        
    Returns:
        {
            "subject": str,
            "email_md": str,
            "dm_md": str,
            "ig_app_url": str
        }
    """
    name = _get_display_name(profile)
    ig_handle = profile.get("ig") or ""
    tt_handle = profile.get("tt") or ""

    # Load markdown templates (use followup templates if this is a followup)
    templates_for_app = _get_templates_for_app(app_key, followup=is_followup, followup_number=followup_number, app_config=app_config)
    key = _normalize_category(category)
    tmpl = templates_for_app.get(key) or {}
    
    # If followup templates not found, fall back to regular templates
    if is_followup and not tmpl:
        templates_for_app = _get_templates_for_app(app_key, followup=False)
        tmpl = templates_for_app.get(key) or {}
    
    link_url = link_url or "https://a17.so/brief"
    link_text = "View brief"

    # Prepare Markdown strings
    email_md = tmpl.get("email_md") or (
        "Hi {name}\n\nBest,\nAbhay\n\n*abhay@a17.so*"
    )
    dm_md = tmpl.get("dm_md") or (
        "Hey {name}!"
    )

    email_md = email_md.format(
        name=name,
        link_url=link_url,
        link_text=link_text,
    )
    dm_md = dm_md.format(name=name)

    subject = tmpl.get("subject") or f"PAID PARTNERSHIP OPPORTUNITY - Pretti App"

    return {
        "subject": subject,
        "email_md": email_md,
        "dm_md": dm_md,
        "ig_app_url": f"instagram://user?username={ig_handle}" if ig_handle else "",
    }

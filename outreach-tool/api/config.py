"""Configuration management for the outreach tool."""

import os
import json
from typing import Dict, Any, Optional

try:
    import yaml
except ImportError:
    yaml = None

from utils import _log


# Category to sheet name mapping
CATEGORY_TO_SHEET = {
    "macro": "Macros",
    "micro": "Micros",
    "submicro": "Submicros",
    "ambassador": "Ambassadors",
    "themepage": "Theme Pages",
    "rawlead": "Raw Leads",
}


def _load_outreach_apps_config() -> Dict[str, Dict[str, str]]:
    """Load outreach apps configuration from env.yaml file."""
    # First try OUTREACH_APPS_JSON env var
    apps_json = os.environ.get("OUTREACH_APPS_JSON", "").strip()
    if apps_json:
        try:
            parsed = json.loads(apps_json)
            if isinstance(parsed, dict):
                _log("config.load.env_var", count=len(parsed))
                return parsed
        except Exception as e:
            _log("config.load.env_var_error", error=str(e))
    
    # Fallback: try to load from env.yaml file
    if yaml is None:
        _log("config.load.no_yaml_library")
        return {}
    
    # Look for env.yaml in the api directory
    api_dir = os.path.dirname(__file__)
    
    # Candidate paths
    candidate_paths = [
        "/app/config/env.yaml",  # Explicit Docker path
        os.path.join(api_dir, "envs", "env.yaml"),  # Local/default path
    ]
    
    env_yaml_path = None
    for p in candidate_paths:
        if os.path.exists(p):
            env_yaml_path = p
            break
    
    if not env_yaml_path:
        # Fallback to default for logging
        env_yaml_path = os.path.join(api_dir, "envs", "env.yaml")
        import sys
        print(f"CRITICAL: env.yaml not found. Searched: {candidate_paths}", file=sys.stderr)
        try:
            print(f"Contents of {api_dir}: {os.listdir(api_dir)}", file=sys.stderr)
            envs_dir = os.path.join(api_dir, "envs")
            if os.path.exists(envs_dir):
                print(f"Contents of {envs_dir}: {os.listdir(envs_dir)}", file=sys.stderr)
        except Exception:
            pass
            
        _log("config.load.no_env_yaml", path=env_yaml_path)
        return {}

    
    try:
        with open(env_yaml_path, "r") as f:
            data = yaml.safe_load(f)
        
        if not isinstance(data, dict):
            _log("config.load.invalid_yaml_format")
            return {}
        
        # Support both new (flat) and old (nested in env_variables) formats
        apps_json_from_file = ""
        
        # Check new format first
        if "OUTREACH_APPS_JSON" in data:
            apps_json_from_file = str(data["OUTREACH_APPS_JSON"]).strip()
            
            # Also load SEARCHAPI_KEY to env if present
            if "SEARCHAPI_KEY" in data:
                 os.environ["SEARCHAPI_KEY"] = str(data["SEARCHAPI_KEY"])
        
        # Fallback to old format
        elif "env_variables" in data and isinstance(data["env_variables"], dict):
            env_vars = data["env_variables"]
            apps_json_from_file = env_vars.get("OUTREACH_APPS_JSON", "").strip()
            
            # Also load SEARCHAPI_KEY from env_variables if present
            if "SEARCHAPI_KEY" in env_vars:
                os.environ["SEARCHAPI_KEY"] = str(env_vars["SEARCHAPI_KEY"])
        
        if not apps_json_from_file:
            _log("config.load.no_apps_in_yaml")
            return {}
        
        parsed = json.loads(apps_json_from_file)
        if isinstance(parsed, dict):
            _log("config.load.yaml_file", count=len(parsed), path=env_yaml_path)
            return parsed
        
        _log("config.load.invalid_apps_format")
        return {}
        
    except Exception as e:
        _log("config.load.yaml_error", error=str(e), path=env_yaml_path)
        return {}


def _get_app_config(app_key: Optional[str]) -> Dict[str, str]:
    """Get configuration for a specific app, with fallback to legacy env vars."""
    from config import _OUTREACH_APPS  # Import the loaded config
    
    # If app_key provided, try to get from OUTREACH_APPS
    if app_key and app_key in _OUTREACH_APPS:
        config = dict(_OUTREACH_APPS[app_key])
        config["app_key"] = app_key
        _log("config.get_app.found", app_key=app_key)
        return config
    
    # Fallback to legacy single-app env vars
    _log("config.get_app.fallback_to_legacy", app_key=app_key or "none")
    return {
        "app_key": app_key or "default",
        "sheets_spreadsheet_id": os.environ.get("SHEETS_SPREADSHEET_ID", ""),
        "gmail_sender": os.environ.get("GMAIL_SENDER", ""),
        "delegated_user": os.environ.get("GOOGLE_DELEGATED_USER", ""),
        "link_url": os.environ.get("LINK_URL", ""),
        "tiktok_account": os.environ.get("TIKTOK_ACCOUNT", ""),
        "instagram_account": os.environ.get("INSTAGRAM_ACCOUNT", ""),
        "from_name": os.environ.get("FROM_NAME", ""),
    }


def _validate_app_config(app_key: str, config: Dict[str, str], strict: bool = False) -> None:
    """Validate that app config has required fields.
    
    Args:
        app_key: The app identifier
        config: The app configuration dict
        strict: If True, raise on missing fields. If False, just log warnings.
    
    Raises:
        ValueError: If strict=True and required fields are missing
    """
    required_fields = ["sheets_spreadsheet_id"]
    missing = [f for f in required_fields if not config.get(f)]
    
    if missing:
        msg = f"App '{app_key}' missing required fields: {missing}"
        if strict:
            _log("config.validate.error", app_key=app_key, missing=missing)
            raise ValueError(msg)
        else:
            _log("config.validate.warning", app_key=app_key, missing=missing)


def _resolve_sender_profile(app_cfg: Dict[str, Any], sender_profile_key: str, strict: bool = False) -> Dict[str, Any]:
    """Resolve sender profile with validation.
    
    Args:
        app_cfg: The app configuration dict
        sender_profile_key: The sender profile identifier to look up
        strict: If True, raise on missing profile. If False, log warning and return original config.
    
    Returns:
        Dict with sender profile overrides applied to app_cfg
    
    Raises:
        ValueError: If strict=True and sender profile not found
    """
    sender_profiles = app_cfg.get("sender_profiles", {})
    
    if not isinstance(sender_profiles, dict):
        msg = f"sender_profiles is not a dict for app '{app_cfg.get('app_key')}'"
        if strict:
            _log("config.sender_profile.invalid_format", app_key=app_cfg.get("app_key"))
            raise ValueError(msg)
        else:
            _log("config.sender_profile.invalid_format_warning", app_key=app_cfg.get("app_key"))
            return app_cfg
    
    if sender_profile_key not in sender_profiles:
        available = list(sender_profiles.keys())
        msg = f"Sender profile '{sender_profile_key}' not found. Available: {available}"
        if strict:
            _log("config.sender_profile.not_found", 
                 sender_profile_key=sender_profile_key,
                 available=available,
                 app_key=app_cfg.get("app_key"))
            raise ValueError(msg)
        else:
            _log("config.sender_profile.not_found_warning",
                 sender_profile_key=sender_profile_key,
                 available=available,
                 app_key=app_cfg.get("app_key"))
            return app_cfg
    
    # Get the sender profile overrides
    profile_overrides = sender_profiles[sender_profile_key]
    if not isinstance(profile_overrides, dict):
        msg = f"Sender profile '{sender_profile_key}' is not a dict"
        if strict:
            _log("config.sender_profile.invalid_profile_format", sender_profile_key=sender_profile_key)
            raise ValueError(msg)
        else:
            _log("config.sender_profile.invalid_profile_format_warning", sender_profile_key=sender_profile_key)
            return app_cfg
    
    # Create a new config with overrides applied
    resolved_cfg = dict(app_cfg)
    resolved_cfg.update(profile_overrides)
    
    # Map friendly names to config keys
    if "email" in profile_overrides:
        resolved_cfg["gmail_sender"] = profile_overrides["email"]
        # Default delegated_user to email if not explicitly set
        if "delegated_user" not in profile_overrides:
            resolved_cfg["delegated_user"] = profile_overrides["email"]
            
    if "instagram" in profile_overrides:
        resolved_cfg["instagram_account"] = profile_overrides["instagram"]
        
    if "tiktok" in profile_overrides:
        resolved_cfg["tiktok_account"] = profile_overrides["tiktok"]
    
    # Ensure from_name matches the profile name if present (mapping 'name' -> 'from_name')
    if "name" in profile_overrides:
        resolved_cfg["from_name"] = profile_overrides["name"]
    
    _log("config.sender_profile.resolved",
         sender_profile_key=sender_profile_key,
         app_key=app_cfg.get("app_key"),
         overrides=list(profile_overrides.keys()))
    
    return resolved_cfg


# Load configuration on module import
_OUTREACH_APPS: Dict[str, Dict[str, str]] = _load_outreach_apps_config()

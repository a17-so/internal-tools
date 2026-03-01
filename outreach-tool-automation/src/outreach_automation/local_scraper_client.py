from __future__ import annotations

import importlib.util
import json
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from outreach_automation.models import ScrapePayload, ScrapeResponse

_SEARCHAPI_URL = "https://www.searchapi.io/api/v1/search"
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+(?:\s*\(at\)\s*|@)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", re.I)
_INSTAGRAM_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?instagram\.com/(?!p/|reel/|stories/|explore/|direct/|accounts/)"
    r"([A-Za-z0-9_.]+)(?=[^A-Za-z0-9_.]|$)",
    re.I,
)
_HANDLE_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")
_BLOCKED_HANDLES = {"media", "instagram", "com", "www"}
_IGNORE_EMAILS = {"example@example.com", "email@example.com", "your@email.com"}


@dataclass(frozen=True, slots=True)
class LocalScrapeSettings:
    searchapi_key: str
    request_timeout_seconds: float
    same_username_fallback: bool
    templates_dir: Path
    outreach_apps_json: str | None


class LocalScrapeClient:
    def __init__(self, settings: LocalScrapeSettings) -> None:
        self._settings = settings

    def scrape(self, payload: ScrapePayload) -> ScrapeResponse:
        username = _extract_tiktok_username(payload.creator_url)
        if not username:
            raise ValueError(f"Invalid TikTok URL, could not extract handle: {payload.creator_url}")

        profile = self._fetch_tiktok_profile(username=username)
        name = _display_name(profile, username=username)
        email = _extract_email(profile.get("bio", "") or "")
        ig_handle = _extract_ig_handle_from_profile(
            profile=profile,
            username=username,
            same_username_fallback=self._settings.same_username_fallback,
        )
        templates = _load_templates(
            app_key=payload.app,
            templates_dir=self._settings.templates_dir,
            outreach_apps_json=self._settings.outreach_apps_json,
            sender_profile=payload.sender_profile,
        )
        comms = _render_comms(templates=templates, category=payload.category, creator_name=name)

        return ScrapeResponse(
            dm_text=comms.dm_text.strip(),
            email_to=email or None,
            email_subject=comms.subject.strip() or f"PAID PROMO OPPORTUNITY - {payload.app.upper()} App",
            email_body_text=comms.email_text.strip(),
            ig_handle=ig_handle or None,
        )

    def _fetch_tiktok_profile(self, *, username: str) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(1, 4):
            try:
                response = requests.get(
                    _SEARCHAPI_URL,
                    params={
                        "engine": "tiktok_profile",
                        "username": username,
                        "api_key": self._settings.searchapi_key,
                    },
                    timeout=self._settings.request_timeout_seconds,
                )
                response.raise_for_status()
                result = response.json()
                profile = result.get("profile")
                if not isinstance(profile, dict):
                    raise RuntimeError(f"SearchAPI returned no profile for @{username}")
                return profile
            except Exception as exc:
                last_exc = exc
                if attempt >= 3 or not _is_retryable_searchapi_error(exc):
                    raise
                # Jittered backoff: ~0.4-0.8s then ~0.8-1.6s
                time.sleep(random.uniform(0.4, 0.8) * (2 ** (attempt - 1)))
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("SearchAPI fetch failed without exception")


@dataclass(frozen=True, slots=True)
class _RenderedComms:
    subject: str
    dm_text: str
    email_text: str


def _extract_tiktok_username(url: str) -> str | None:
    path = (urlparse(url).path or "").strip()
    match = re.search(r"/@([A-Za-z0-9_.-]+)", path)
    if not match:
        return None
    handle = match.group(1).strip().lstrip("@")
    return handle or None


def _is_retryable_searchapi_error(exc: Exception) -> bool:
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True
    if isinstance(exc, requests.HTTPError):
        status = exc.response.status_code if exc.response is not None else None
        if status is None:
            return True
        return status == 429 or status >= 500
    return False


def _extract_email(text: str) -> str:
    match = _EMAIL_RE.search(text or "")
    if not match:
        return ""
    email = match.group(0).replace("(at)", "@").replace(" ", "")
    return "" if email.lower() in _IGNORE_EMAILS else email


def _is_valid_handle(value: str) -> bool:
    normalized = (value or "").strip().lstrip("@")
    if not normalized:
        return False
    lower = normalized.lower()
    if lower in _BLOCKED_HANDLES:
        return False
    if "." in normalized and any(
        tld in lower for tld in [".com", ".org", ".net", ".io", ".co", ".ee", ".ai", ".be", ".bio", ".cc", ".ke"]
    ):
        return False
    return bool(_HANDLE_RE.match(normalized))


def _extract_ig_from_text(value: str) -> str:
    if not value:
        return ""
    match = _INSTAGRAM_URL_RE.search(value)
    if not match:
        return ""
    handle = (match.group(1) or "").strip().lstrip("@")
    return handle if _is_valid_handle(handle) else ""


def _extract_ig_handle_from_profile(
    *,
    profile: dict[str, Any],
    username: str,
    same_username_fallback: bool,
) -> str:
    bio = str(profile.get("bio", "") or "")

    for pattern in (
        r"(?:^|[\s,;|])(?:ig|insta|instagram)\s*[:\-]\s*@?([A-Za-z0-9_.]{1,30})\b",
        r"(?:^|[\s,;|])(?:ig|insta|instagram)\s+@([A-Za-z0-9_.]{1,30})\b",
        r"@([A-Za-z0-9_.]{1,30})\b",
    ):
        match = re.search(pattern, bio, re.I)
        if not match:
            continue
        handle = (match.group(1) or "").strip().lstrip("@")
        if _is_valid_handle(handle):
            return handle

    bio_link = str(profile.get("bio_link", "") or "")
    from_link = _extract_ig_from_text(bio_link)
    if from_link:
        return from_link

    if same_username_fallback and _is_valid_handle(username):
        return username
    return ""


def _display_name(profile: dict[str, Any], *, username: str) -> str:
    tt_username = str(profile.get("username") or "").strip()
    if tt_username:
        return tt_username.lower()
    name = str(profile.get("name") or "").strip()
    if name and name.lower() not in {"tiktok", "tiktok - make your day"}:
        return name
    return username.lower()


def _load_templates(
    *,
    app_key: str,
    templates_dir: Path,
    outreach_apps_json: str | None,
    sender_profile: str,
) -> dict[str, dict[str, str]]:
    app_key_normalized = (app_key or "").strip().lower()
    script_file = templates_dir / f"{app_key_normalized}.py"
    if not script_file.exists():
        raise RuntimeError(f"Template script not found: {script_file}")

    spec = importlib.util.spec_from_file_location(f"local_templates_{app_key_normalized}", script_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load template script: {script_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    get_templates = getattr(module, "get_templates", None)
    if not callable(get_templates):
        raise RuntimeError(f"Template script missing get_templates(): {script_file}")

    app_config = _resolve_app_config(outreach_apps_json=outreach_apps_json, app_key=app_key_normalized, sender_profile=sender_profile)
    rendered = get_templates(app_name=app_key.upper(), app_config=app_config)
    if not isinstance(rendered, dict):
        raise RuntimeError(f"Invalid templates shape from: {script_file}")
    return rendered


def _resolve_app_config(*, outreach_apps_json: str | None, app_key: str, sender_profile: str) -> dict[str, str]:
    if not outreach_apps_json:
        return {}
    try:
        parsed = json.loads(outreach_apps_json)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}

    app_cfg_raw = parsed.get(app_key)
    if not isinstance(app_cfg_raw, dict):
        return {}

    app_cfg = dict(app_cfg_raw)
    sender_profiles = app_cfg_raw.get("sender_profiles")
    if isinstance(sender_profiles, dict):
        profile_overrides = sender_profiles.get(sender_profile)
        if isinstance(profile_overrides, dict):
            app_cfg.update(profile_overrides)
    return {k: str(v) for k, v in app_cfg.items() if isinstance(v, (str, int, float, bool))}


def _render_comms(*, templates: dict[str, dict[str, str]], category: str, creator_name: str) -> _RenderedComms:
    key = (category or "").strip().lower()
    entry = templates.get(key) or templates.get("submicro") or next(iter(templates.values()), {})
    subject = str(entry.get("subject") or "")
    email_md = str(entry.get("email_md") or "")
    dm_md = str(entry.get("dm_md") or "")
    email_text = email_md.format(name=creator_name)
    dm_text = dm_md.format(name=creator_name)
    return _RenderedComms(subject=subject, dm_text=dm_text, email_text=email_text)

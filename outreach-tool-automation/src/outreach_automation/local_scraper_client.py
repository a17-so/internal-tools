from __future__ import annotations

import importlib.util
import json
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

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
_LINK_HUB_DOMAINS = {
    "linktr.ee",
    "beacons.ai",
    "beacons.page",
    "campsite.bio",
    "msha.ke",
    "bio.site",
    "tap.bio",
    "hoo.be",
    "allmylinks.com",
    "lnk.to",
    "carrd.co",
    "lnk.bio",
    "solo.to",
    "stan.store",
    "withkoji.com",
}
_LINK_CRAWL_TIMEOUT_SECONDS = 3.0
_LINK_CRAWL_MAX_BYTES = 200_000


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
        bio_link = str(profile.get("bio_link", "") or "")
        if bio_link and (not email or not ig_handle):
            link_email, link_ig = _extract_contact_from_link_page(bio_link)
            if not email and link_email:
                email = link_email
            if not ig_handle and link_ig:
                ig_handle = link_ig
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


def _extract_contact_from_link_page(link_url: str) -> tuple[str, str]:
    parsed = urlparse((link_url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        return "", ""
    host = (parsed.netloc or "").lower().replace("www.", "")
    if host not in _LINK_HUB_DOMAINS:
        return "", ""

    try:
        response = requests.get(
            link_url,
            timeout=_LINK_CRAWL_TIMEOUT_SECONDS,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                )
            },
            allow_redirects=True,
            stream=True,
        )
        response.raise_for_status()
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_content(chunk_size=8192):
            if not chunk:
                continue
            chunks.append(chunk)
            total += len(chunk)
            if total >= _LINK_CRAWL_MAX_BYTES:
                break

        html = b"".join(chunks).decode("utf-8", errors="ignore")
        if not html:
            return "", ""
        decoded = unquote(html)
        email = _extract_email(html) or _extract_email(decoded)
        ig = _extract_ig_from_text(html) or _extract_ig_from_text(decoded)
        return email, ig
    except Exception:
        return "", ""


def _extract_email(text: str) -> str:
    raw = text or ""
    normalized = _normalize_obfuscated_email(raw)
    match = _EMAIL_RE.search(raw) or _EMAIL_RE.search(normalized)
    if not match:
        return ""
    email = match.group(0).replace("(at)", "@").replace(" ", "")
    return "" if email.lower() in _IGNORE_EMAILS else email


def _normalize_obfuscated_email(value: str) -> str:
    text = value
    text = re.sub(r"\s+at\s+", "@", text, flags=re.I)
    text = re.sub(r"\s+dot\s+", ".", text, flags=re.I)
    text = re.sub(r"\(at\)", "@", text, flags=re.I)
    text = re.sub(r"\(dot\)", ".", text, flags=re.I)
    return text


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
    defaults: dict[str, str] = {
        "from_name": _default_from_name(sender_profile),
    }
    if not outreach_apps_json:
        return defaults
    try:
        parsed = json.loads(outreach_apps_json)
    except json.JSONDecodeError:
        return defaults
    if not isinstance(parsed, dict):
        return defaults

    app_cfg_raw = parsed.get(app_key)
    if not isinstance(app_cfg_raw, dict):
        return defaults

    app_cfg = dict(app_cfg_raw)
    sender_profiles = app_cfg_raw.get("sender_profiles")
    if isinstance(sender_profiles, dict):
        profile_overrides = sender_profiles.get(sender_profile)
        if isinstance(profile_overrides, dict):
            app_cfg.update(profile_overrides)
    resolved = {k: str(v) for k, v in app_cfg.items() if isinstance(v, (str, int, float, bool))}
    resolved.setdefault("from_name", defaults["from_name"])
    return resolved


def _default_from_name(sender_profile: str) -> str:
    normalized = sender_profile.strip().lower()
    if normalized == "ethan":
        return "Ethan"
    if normalized == "abhay":
        return "Abhay Chebium"
    if normalized == "advaith":
        return "Advaith"
    if not normalized:
        return "Team"
    return normalized.replace("_", " ").replace("-", " ").title()


def _render_comms(*, templates: dict[str, dict[str, str]], category: str, creator_name: str) -> _RenderedComms:
    key = (category or "").strip().lower()
    entry = templates.get(key) or templates.get("submicro") or next(iter(templates.values()), {})
    subject = str(entry.get("subject") or "")
    email_md = str(entry.get("email_md") or "")
    dm_md = str(entry.get("dm_md") or "")
    email_text = email_md.format(name=creator_name)
    dm_text = dm_md.format(name=creator_name)
    return _RenderedComms(subject=subject, dm_text=dm_text, email_text=email_text)

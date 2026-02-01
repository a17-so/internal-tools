"""Email operations for the outreach tool."""

import os
import base64
from typing import Dict, Any, Optional
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from utils import _log
from google_services import _gmail_client


def _send_email(
    subject: str,
    body_text: str,
    to_email: str,
    from_email_override: Optional[str] = None,
    delegated_user_override: Optional[str] = None,
    body_html: Optional[str] = None,
    from_name: Optional[str] = None,
    reply_to: Optional[str] = None,
    list_unsubscribe: Optional[str] = None,
    to_name: Optional[str] = None
) -> Dict[str, Any]:
    """Send an email via Gmail API.
    
    Args:
        subject: Email subject line
        body_text: Plain text email body
        to_email: Recipient email address
        from_email_override: Optional override for sender email
        delegated_user_override: Optional override for delegated user
        body_html: Optional HTML email body
        from_name: Optional sender name
        reply_to: Optional reply-to address
        list_unsubscribe: Optional unsubscribe link
        to_name: Optional recipient name
        
    Returns:
        {"ok": bool, "result": dict or None, "error": str or None}
    """
    if not to_email:
        return {"ok": False, "error": "No recipient email"}

    try:
        client_info = _gmail_client(delegated_user_override=delegated_user_override)
    except Exception as e:
        _log("gmail.client_init.error", error=str(e))
        return {"ok": False, "error": f"Gmail client init failed: {e}"}
    
    if not client_info:
        return {"ok": False, "error": "Gmail client not configured"}
    
    gmail, user_id = client_info

    from_email = (
        from_email_override
        or os.environ.get("GMAIL_SENDER")
        or (user_id if isinstance(user_id, str) else "")
    )

    try:
        _log(
            "gmail.send.prepare",
            to=to_email,
            subject=subject,
            has_html=bool(body_html),
            has_text=bool(body_text),
            from_email=bool(from_email),
        )
        
        if body_html is not None:
            msg = MIMEMultipart("alternative")
            if body_text:
                msg.attach(MIMEText(body_text, "plain", "utf-8"))
            msg.attach(MIMEText(body_html, "html", "utf-8"))
        else:
            msg = MIMEText(body_text or "", "plain", "utf-8")

        # Headers
        if from_email:
            msg["From"] = formataddr((from_name, from_email)) if from_name else from_email
        if reply_to:
            msg["Reply-To"] = reply_to
        if list_unsubscribe:
            try:
                # Ensure RFC-compliant angle brackets around URIs
                parts = []
                for token in str(list_unsubscribe).split(","):
                    t = token.strip()
                    if not t:
                        continue
                    if not (t.startswith("<") and t.endswith(">")):
                        t = f"<{t}>"
                    parts.append(t)
                if parts:
                    msg["List-Unsubscribe"] = ", ".join(parts)
            except Exception:
                pass

        msg["To"] = formataddr((to_name, to_email)) if to_name else to_email
        msg["Subject"] = subject

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        _log("gmail.send.request", user_id=user_id)
        resp = gmail.users().messages().send(userId=user_id, body={"raw": raw}).execute()
        _log("gmail.send.success", id=(resp or {}).get("id"), labelIds=(resp or {}).get("labelIds"))
        return {"ok": True, "result": resp}
    except Exception as e:
        _log("gmail.send.error", error=str(e))
        return {"ok": False, "error": str(e)}

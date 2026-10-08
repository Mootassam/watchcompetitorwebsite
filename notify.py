"""
Outbound notifications for RivalRadar: webhooks (POST JSON with an optional HMAC
signature) and optional email alerts via the user's own SMTP. Failures never
interrupt a scan.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import smtplib
import ssl
import threading
import time
from email.message import EmailMessage

import requests

import store


def _event_match(events: str, type_: str) -> bool:
    events = (events or "all").strip().lower()
    if events in ("", "all", "*"):
        return True
    return type_ in {e.strip() for e in events.split(",")}


def _sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _post(hook: dict, payload: dict):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "RivalRadar-Webhook/1.0"}
    if hook.get("secret"):
        headers["X-RivalRadar-Signature"] = _sign(hook["secret"], body)
    try:
        r = requests.post(hook["url"], data=body, headers=headers, timeout=12)
        store.update_webhook(hook["id"], last_status=f"{r.status_code}", last_fired=time.time())
    except Exception as e:
        store.update_webhook(hook["id"], last_status=f"error: {e}"[:120], last_fired=time.time())


def dispatch(type_: str, comp: dict, summary: str, url: str = "", detail=""):
    """Fire all matching webhooks (async) and send an email if configured."""
    payload = {
        "event": type_, "competitor": comp.get("name"), "domain": comp.get("domain"),
        "summary": summary, "url": url,
        "detail": detail if isinstance(detail, str) else json.dumps(detail),
        "timestamp": int(time.time()),
    }
    for hook in store.webhooks(active_only=True):
        if _event_match(hook.get("events", "all"), type_):
            threading.Thread(target=_post, args=(hook, payload), daemon=True).start()

    st = store.get_settings()
    if st.get("smtp_host") and st.get("alert_email"):
        threading.Thread(target=_email, args=(st, comp, summary, url), daemon=True).start()


def _email(st, comp, summary, url):
    try:
        msg = EmailMessage()
        msg["From"] = st.get("smtp_from") or st.get("smtp_user")
        msg["To"] = st["alert_email"]
        msg["Subject"] = f"[RivalRadar] {comp.get('name')}: {summary}"[:180]
        msg.set_content(f"{comp.get('name')} ({comp.get('domain')})\n\n{summary}\n\n{url}\n\n— RivalRadar")
        port = int(float(st.get("smtp_port") or 587))
        sec = (st.get("smtp_security") or "starttls").lower()
        if sec == "ssl":
            s = smtplib.SMTP_SSL(st["smtp_host"], port, timeout=20, context=ssl.create_default_context())
        else:
            s = smtplib.SMTP(st["smtp_host"], port, timeout=20)
            s.ehlo()
            if sec == "starttls":
                s.starttls(context=ssl.create_default_context())
                s.ehlo()
        if st.get("smtp_user"):
            s.login(st["smtp_user"], st.get("smtp_pass", ""))
        s.send_message(msg)
        s.quit()
    except Exception:
        pass


def test_webhook(url: str, secret: str = "") -> dict:
    payload = {"event": "test", "competitor": "RivalRadar", "domain": "example.com",
               "summary": "This is a test event from RivalRadar.", "timestamp": int(time.time())}
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "RivalRadar-Webhook/1.0"}
    if secret:
        headers["X-RivalRadar-Signature"] = _sign(secret, body)
    try:
        r = requests.post(url, data=body, headers=headers, timeout=12)
        return {"ok": r.status_code < 400, "status": r.status_code,
                "body": (r.text or "")[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def test_email(st) -> dict:
    try:
        comp = {"name": "RivalRadar test", "domain": "example.com"}
        _email(st, comp, "Test alert — your email settings work.", "")
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}

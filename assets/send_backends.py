#!/usr/bin/env python3
"""Pluggable send backends (PLAN.md §7).

Each backend exposes:
    send(draft: dict, *, cfg: dict, dry_run: bool=False) -> dict

draft schema (subset of assets/drafts_schema.json + extras):
    to_email, to_name, subject, body_text, body_html,
    in_reply_to (Message-ID of original mail; for threading),
    references (list of Message-IDs for References header; defaults to [in_reply_to]),
    gmail_id (original Gmail message id, for mark-read in caller),
    thread_id (Gmail threadId; required for gws_drafts to attach to correct thread)

cfg keys (read from inbox config.yaml; surfaced to caller):
    send.backend                — gws_drafts | gws_send | sendgrid (MVP)
    send.from_email             — required for gws_send / sendgrid
    send.from_name              — display name (e.g., "스터디파이")
    send.bcc                    — optional self-BCC for audit (Pin-3 graduation tracking)
    send.sendgrid.api_key_env   — env var name holding the SendGrid API key

Returns dict { backend, status, id?, error? } — caller logs to metrics.
"""
from __future__ import annotations

import base64
import datetime as _dt
import email.utils
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any, Callable


# ---------------------------------------------------------------------------
# RFC 2822 message construction (shared by gws_drafts / gws_send)
# ---------------------------------------------------------------------------
def _build_rfc2822(draft: dict, cfg: dict) -> str:
    """Build a multipart/alternative RFC 2822 message string."""
    boundary = f"=_part_{_dt.datetime.utcnow().strftime('%Y%m%d%H%M%S')}_=" \
               + base64.urlsafe_b64encode(os.urandom(6)).decode().rstrip("=")
    from_email = cfg.get("send", {}).get("from_email", "")
    from_name = cfg.get("send", {}).get("from_name", "")
    bcc = cfg.get("send", {}).get("bcc", "")
    to_email = draft["to_email"]
    to_name = draft.get("to_name", "")
    subject = draft["subject"]
    in_reply_to = draft.get("in_reply_to", "")
    references = draft.get("references") or ([in_reply_to] if in_reply_to else [])

    from_hdr = email.utils.formataddr((from_name, from_email)) if from_name else from_email
    to_hdr = email.utils.formataddr((to_name, to_email)) if to_name else to_email
    msgid = email.utils.make_msgid(domain=(from_email.split("@", 1)[1] if "@" in from_email else "localhost"))
    date = email.utils.formatdate(localtime=True)

    headers = [
        f"From: {from_hdr}",
        f"To: {to_hdr}",
        f"Subject: {_encode_header(subject)}",
        f"Date: {date}",
        f"Message-ID: {msgid}",
        "MIME-Version: 1.0",
        f"Content-Type: multipart/alternative; boundary=\"{boundary}\"",
    ]
    if bcc:
        headers.append(f"Bcc: {bcc}")
    if in_reply_to:
        headers.append(f"In-Reply-To: {in_reply_to}")
    if references:
        headers.append(f"References: {' '.join(references)}")

    parts = [
        f"--{boundary}",
        "Content-Type: text/plain; charset=UTF-8",
        "Content-Transfer-Encoding: 8bit",
        "",
        draft.get("body_text", ""),
        "",
        f"--{boundary}",
        "Content-Type: text/html; charset=UTF-8",
        "Content-Transfer-Encoding: 8bit",
        "",
        draft.get("body_html", ""),
        "",
        f"--{boundary}--",
        "",
    ]
    return "\r\n".join(headers) + "\r\n\r\n" + "\r\n".join(parts)


def _encode_header(s: str) -> str:
    """RFC 2047 Q-encode if non-ASCII, else passthrough."""
    try:
        s.encode("ascii")
        return s
    except UnicodeEncodeError:
        b64 = base64.b64encode(s.encode("utf-8")).decode("ascii")
        return f"=?UTF-8?B?{b64}?="


# ---------------------------------------------------------------------------
# Backend: gws_drafts (DEFAULT — creates Gmail draft only, user sends manually)
# ---------------------------------------------------------------------------
def send_gws_drafts(draft: dict, *, cfg: dict, dry_run: bool = False) -> dict:
    raw = _build_rfc2822(draft, cfg)
    raw_b64 = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")
    params: dict[str, Any] = {
        "userId": "me",
        "body": {"message": {"raw": raw_b64}},
    }
    if draft.get("thread_id"):
        params["body"]["message"]["threadId"] = draft["thread_id"]
    if dry_run:
        return {"backend": "gws_drafts", "status": "dry_run", "id": None,
                "preview_first_line": (draft.get("body_text") or "").splitlines()[:1]}
    return _gws_call(["gws", "gmail", "users", "drafts", "create",
                      "--params", json.dumps(params)], "gws_drafts")


# ---------------------------------------------------------------------------
# Backend: gws_send (graduation backend — actually sends via Gmail)
# ---------------------------------------------------------------------------
def send_gws_send(draft: dict, *, cfg: dict, dry_run: bool = False) -> dict:
    raw = _build_rfc2822(draft, cfg)
    raw_b64 = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")
    params: dict[str, Any] = {
        "userId": "me",
        "body": {"raw": raw_b64},
    }
    if draft.get("thread_id"):
        params["body"]["threadId"] = draft["thread_id"]
    if dry_run:
        return {"backend": "gws_send", "status": "dry_run", "id": None}
    return _gws_call(["gws", "gmail", "users", "messages", "send",
                      "--params", json.dumps(params)], "gws_send")


def _gws_call(cmd: list[str], backend_name: str) -> dict:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return {"backend": backend_name, "status": "error", "error": str(e)}
    if proc.returncode != 0:
        return {"backend": backend_name, "status": "error",
                "error": (proc.stderr or proc.stdout or "").strip()[:500]}
    out_id = ""
    try:
        parsed = json.loads(proc.stdout)
        out_id = parsed.get("id") or parsed.get("message", {}).get("id") or ""
    except (json.JSONDecodeError, AttributeError):
        pass
    return {"backend": backend_name, "status": "ok", "id": out_id}


# ---------------------------------------------------------------------------
# Backend: sendgrid (legacy — for users with their own SendGrid account)
# ---------------------------------------------------------------------------
def send_sendgrid(draft: dict, *, cfg: dict, dry_run: bool = False) -> dict:
    sg_cfg = cfg.get("send", {})
    api_key_env = sg_cfg.get("sendgrid", {}).get("api_key_env", "SENDGRID_API_KEY")
    api_key = os.environ.get(api_key_env)
    if not api_key:
        return {"backend": "sendgrid", "status": "error",
                "error": f"env {api_key_env} not set"}
    in_reply_to = draft.get("in_reply_to", "")
    headers: dict[str, str] = {}
    if in_reply_to:
        headers["In-Reply-To"] = in_reply_to
        refs = draft.get("references") or [in_reply_to]
        headers["References"] = " ".join(refs)
    personalization: dict[str, Any] = {
        "to": [{"email": draft["to_email"], "name": draft.get("to_name", "")}],
        "subject": draft["subject"],
    }
    if headers:
        personalization["headers"] = headers
    if sg_cfg.get("bcc"):
        personalization["bcc"] = [{"email": sg_cfg["bcc"]}]
    payload = {
        "personalizations": [personalization],
        "from": {"email": sg_cfg.get("from_email", ""), "name": sg_cfg.get("from_name", "")},
        "subject": draft["subject"],
        "content": [
            {"type": "text/plain", "value": draft.get("body_text", "")},
            {"type": "text/html", "value": draft.get("body_html", "")},
        ],
    }
    if dry_run:
        return {"backend": "sendgrid", "status": "dry_run",
                "preview_to": draft["to_email"]}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=data,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return {"backend": "sendgrid", "status": "ok",
                    "id": resp.headers.get("X-Message-Id", ""),
                    "http_status": resp.status}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"backend": "sendgrid", "status": "error",
                "http_status": e.code, "error": body[:500]}
    except (urllib.error.URLError, TimeoutError) as e:
        return {"backend": "sendgrid", "status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
BACKENDS: dict[str, Callable[..., dict]] = {
    "gws_drafts": send_gws_drafts,
    "gws_send": send_gws_send,
    "sendgrid": send_sendgrid,
}


def dispatch(draft: dict, *, cfg: dict, dry_run: bool = False) -> dict:
    name = (cfg.get("send", {}).get("backend") or "gws_drafts").lower()
    backend = BACKENDS.get(name)
    if backend is None:
        return {"backend": name, "status": "error",
                "error": f"unknown backend; choose one of {sorted(BACKENDS)}"}
    return backend(draft, cfg=cfg, dry_run=dry_run)


# ---------------------------------------------------------------------------
# Selftest — exercises RFC 2822 build + dispatch dry-run path only
# ---------------------------------------------------------------------------
def _selftest() -> int:
    cfg = {
        "send": {
            "backend": "gws_drafts",
            "from_email": "support@example.com",
            "from_name": "Example Support",
            "bcc": "support@example.com",
        }
    }
    d = {
        "to_email": "user@example.org",
        "to_name": "홍길동",
        "subject": "Re: 안녕하세요 — 테스트",
        "body_text": "안녕하세요\n\n감사합니다.\n",
        "body_html": "<p>안녕하세요</p><p>감사합니다.</p>",
        "in_reply_to": "<orig@example.org>",
        "thread_id": "thread123",
    }
    raw = _build_rfc2822(d, cfg)
    fails = 0
    checks = [
        ("From header present", "From:" in raw),
        ("Bcc header present", "Bcc: support@example.com" in raw),
        ("In-Reply-To present", "In-Reply-To: <orig@example.org>" in raw),
        ("References derived from In-Reply-To", "References: <orig@example.org>" in raw),
        ("Korean subject Q-encoded (=?UTF-8?B?)", "=?UTF-8?B?" in raw),
        ("multipart boundary marker", "--=_part_" in raw),
    ]
    for label, ok in checks:
        print(f"[{'OK' if ok else 'FAIL'}] {label}")
        if not ok:
            fails += 1
    res = dispatch(d, cfg=cfg, dry_run=True)
    ok = res.get("status") == "dry_run" and res.get("backend") == "gws_drafts"
    print(f"[{'OK' if ok else 'FAIL'}] dispatch dry_run -> {res}")
    if not ok:
        fails += 1
    res2 = dispatch(d, cfg={"send": {"backend": "nonexistent"}}, dry_run=True)
    ok2 = res2.get("status") == "error"
    print(f"[{'OK' if ok2 else 'FAIL'}] unknown backend errors -> {res2}")
    if not ok2:
        fails += 1
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(_selftest())

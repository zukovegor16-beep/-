from __future__ import annotations

import imaplib
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email import message_from_bytes
from email.utils import parsedate_to_datetime
from typing import Callable

from tiktok_publisher.config import AppSettings
from tiktok_publisher.email_code import extract_verification_code

logger = logging.getLogger(__name__)

PROVIDER_IMAP: dict[str, tuple[str, int]] = {
    "gmail": ("imap.gmail.com", 993),
    "outlook": ("outlook.office365.com", 993),
    "mail_ru": ("imap.mail.ru", 993),
}

DEFAULT_FROM_HINTS = ("tiktok", "noreply", "account.tiktok", "mail.tiktok")


@dataclass(frozen=True)
class ImapCodeResult:
    code: str
    uid: str
    subject: str


def imap_host_for_settings(settings: AppSettings) -> tuple[str, int, bool]:
    ob = settings.onboard
    if ob.imap_host:
        return ob.imap_host, ob.imap_port, ob.imap_use_ssl
    host, port = PROVIDER_IMAP.get(ob.email_provider, ("imap.gmail.com", 993))
    return host, port, ob.imap_use_ssl


def _decode_part(part) -> str:
    payload = part.get_payload(decode=True)
    if not payload:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def _message_text(msg) -> str:
    chunks: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype in ("text/plain", "text/html"):
                chunks.append(_decode_part(part))
    else:
        chunks.append(_decode_part(msg))
    return "\n".join(chunks)


def _imap_since_date(since_unix: float) -> str:
    dt = datetime.fromtimestamp(since_unix, tz=timezone.utc)
    return dt.strftime("%d-%b-%Y")


def _from_matches(from_header: str, hints: tuple[str, ...]) -> bool:
    low = (from_header or "").lower()
    return any(h in low for h in hints)


def _message_internal_ts(msg) -> float:
    raw = msg.get("Date")
    if not raw:
        return 0.0
    try:
        return parsedate_to_datetime(raw).timestamp()
    except Exception:
        return 0.0


def wait_for_verification_code_imap(
    settings: AppSettings,
    email: str,
    email_password: str,
    *,
    since_unix: float | None = None,
    code_extractor: Callable[[str], str | None] | None = None,
    mark_read: bool = False,
) -> ImapCodeResult | None:
    host, port, use_ssl = imap_host_for_settings(settings)
    pattern = settings.onboard.email_code_regex
    extract = code_extractor or (
        lambda t: extract_verification_code(t, pattern=pattern)
    )
    since = since_unix or (time.time() - 120)
    since_date = _imap_since_date(since)
    from_hints = DEFAULT_FROM_HINTS
    deadline = time.time() + settings.onboard.email_code_timeout_sec

    while time.time() < deadline:
        try:
            conn = imaplib.IMAP4_SSL(host, port) if use_ssl else imaplib.IMAP4(host, port)
            conn.login(email, email_password)
            conn.select("INBOX")
            typ, data = conn.search(None, "SINCE", since_date)
            if typ != "OK":
                conn.logout()
                time.sleep(6)
                continue
            uids = data[0].split() if data and data[0] else []
            candidates: list[tuple[float, bytes, str, str]] = []
            for uid in uids:
                typ, msg_data = conn.fetch(uid, "(RFC822)")
                if typ != "OK" or not msg_data:
                    continue
                raw = msg_data[0][1]
                msg = message_from_bytes(raw)
                ts = _message_internal_ts(msg)
                if ts and ts < since - 5:
                    continue
                subj = str(msg.get("Subject", ""))
                from_h = str(msg.get("From", ""))
                if not _from_matches(from_h, from_hints) and "tiktok" not in subj.lower():
                    continue
                text = _message_text(msg)
                code = extract(text)
                if code:
                    candidates.append((ts or time.time(), uid, code, subj))
            conn.logout()
            if candidates:
                candidates.sort(key=lambda x: x[0])
                _ts, uid, code, subj = candidates[-1]
                uid_str = uid.decode() if isinstance(uid, bytes) else str(uid)
                if mark_read:
                    mark_imap_message_seen(settings, email, email_password, uid_str)
                return ImapCodeResult(code=code, uid=uid_str, subject=subj)
        except Exception as e:
            logger.warning("IMAP poll: %s", e)
        time.sleep(8)
    return None


def probe_imap_login(settings: AppSettings, email: str, email_password: str) -> tuple[bool, str]:
    """Quick IMAP login check for preflight."""
    if not email.strip() or not email_password.strip():
        return False, "email or password empty"
    host, port, use_ssl = imap_host_for_settings(settings)
    try:
        conn = imaplib.IMAP4_SSL(host, port) if use_ssl else imaplib.IMAP4(host, port)
        conn.login(email, email_password)
        conn.select("INBOX")
        conn.logout()
        return True, "ok"
    except Exception as e:
        return False, str(e)


def mark_imap_message_seen(
    settings: AppSettings,
    email: str,
    email_password: str,
    uid: str,
) -> bool:
    host, port, use_ssl = imap_host_for_settings(settings)
    try:
        conn = imaplib.IMAP4_SSL(host, port) if use_ssl else imaplib.IMAP4(host, port)
        conn.login(email, email_password)
        conn.select("INBOX")
        conn.store(uid.encode() if isinstance(uid, str) else uid, "+FLAGS", "\\Seen")
        conn.logout()
        return True
    except Exception as e:
        logger.warning("mark_imap_message_seen: %s", e)
        return False

from __future__ import annotations

import imaplib
import logging
import time
from email import message_from_bytes
from typing import Callable

from tiktok_publisher.config import AppSettings
from tiktok_publisher.email_code import extract_verification_code

logger = logging.getLogger(__name__)

PROVIDER_IMAP: dict[str, tuple[str, int]] = {
    "gmail": ("imap.gmail.com", 993),
    "outlook": ("outlook.office365.com", 993),
    "mail_ru": ("imap.mail.ru", 993),
}


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


def wait_for_verification_code_imap(
    settings: AppSettings,
    email: str,
    email_password: str,
    *,
    since_unix: float | None = None,
    code_extractor: Callable[[str], str | None] | None = None,
) -> str | None:
    host, port, use_ssl = imap_host_for_settings(settings)
    pattern = settings.onboard.email_code_regex
    extract = code_extractor or (
        lambda t: extract_verification_code(t, pattern=pattern)
    )
    deadline = time.time() + settings.onboard.email_code_timeout_sec
    seen_uids: set[bytes] = set()

    while time.time() < deadline:
        try:
            if use_ssl:
                conn = imaplib.IMAP4_SSL(host, port)
            else:
                conn = imaplib.IMAP4(host, port)
            conn.login(email, email_password)
            conn.select("INBOX")
            typ, data = conn.search(None, "UNSEEN")
            if typ != "OK":
                conn.logout()
                time.sleep(5)
                continue
            uids = data[0].split() if data and data[0] else []
            for uid in reversed(uids):
                if uid in seen_uids:
                    continue
                typ, msg_data = conn.fetch(uid, "(RFC822)")
                if typ != "OK" or not msg_data:
                    continue
                raw = msg_data[0][1]
                msg = message_from_bytes(raw)
                text = _message_text(msg)
                code = extract(text)
                if code:
                    conn.store(uid, "+FLAGS", "\\Seen")
                    conn.logout()
                    return code
                seen_uids.add(uid)
            conn.logout()
        except Exception as e:
            logger.warning("IMAP poll: %s", e)
        time.sleep(8)
    return None

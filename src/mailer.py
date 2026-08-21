"""Email notification via SMTP (STARTTLS).

Sends one summary email per run listing every notified product. If SMTP
credentials or a recipient are not configured, sending is skipped with a
log message instead of raising, so a missing secret never breaks the
scraping pipeline.
"""

from __future__ import annotations

import html
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import MAIL_FROM, MAIL_TO, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER
from src.product import Product

logger = logging.getLogger(__name__)


def _build_subject(products: list[Product], subject_prefix: str) -> str:
    return f"{subject_prefix} 注目商品 {len(products)}件を検知"


def _build_text_body(products: list[Product]) -> str:
    lines: list[str] = []

    for p in products:
        lines.append(p.name)
        lines.append(f"  現在価格     : ¥{p.price:,}")

        if p.was_price:
            lines.append(f"  定価         : ¥{p.was_price:,}")

        lines.append(f"  割引率       : {p.discount:.1f}%")

        if p.expected_price:
            lines.append(f"  AI査定価格   : ¥{p.expected_price:,}")

        if p.mercari_price:
            lines.append(f"  メルカリ相場 : ¥{p.mercari_price:,}")

        lines.append(f"  利益         : ¥{p.profit:,}")
        lines.append(f"  グレード     : {p.grade}")
        lines.append(f"  URL          : {p.url}")
        lines.append("")

    return "\n".join(lines)


def _build_html_body(products: list[Product]) -> str:
    rows = []

    for p in products:
        expected = f"¥{p.expected_price:,}" if p.expected_price else "-"
        mercari = f"¥{p.mercari_price:,}" if p.mercari_price else "-"

        rows.append(
            "<tr>"
            f'<td><a href="{html.escape(p.url)}">{html.escape(p.name)}</a></td>'
            f"<td>¥{p.price:,}</td>"
            f"<td>¥{p.was_price:,}</td>"
            f"<td>{p.discount:.1f}%</td>"
            f"<td>{expected}</td>"
            f"<td>{mercari}</td>"
            f"<td>¥{p.profit:,}</td>"
            f"<td>{html.escape(p.grade)}</td>"
            "</tr>"
        )

    table = (
        '<table border="1" cellspacing="0" cellpadding="6">'
        "<tr>"
        "<th>商品名</th><th>現在価格</th><th>定価</th><th>割引率</th>"
        "<th>AI査定</th><th>メルカリ相場</th>"
        "<th>利益</th><th>グレード</th>"
        "</tr>" + "".join(rows) + "</table>"
    )

    return f"<html><body>{table}</body></html>"


def send_notification_email(
    products: list[Product],
    mail_to: str = MAIL_TO,
    subject_prefix: str = "[JD Monitor]",
) -> None:
    """Send a single summary email listing every notified product.

    No-op (logged, not raised) if there is nothing to send or SMTP is
    not configured, so a missing secret never fails the pipeline.
    """
    if not products:
        logger.info("No products to notify by email")
        return

    if not (SMTP_USER and SMTP_PASSWORD and mail_to):
        logger.warning(
            "SMTP not configured (SMTP_USER/SMTP_PASSWORD/mail_to); "
            "skipping email notification"
        )
        return

    message = MIMEMultipart("alternative")
    message["Subject"] = _build_subject(products, subject_prefix)
    message["From"] = MAIL_FROM
    message["To"] = mail_to

    message.attach(MIMEText(_build_text_body(products), "plain", "utf-8"))
    message.attach(MIMEText(_build_html_body(products), "html", "utf-8"))

    recipients = [addr.strip() for addr in mail_to.split(",") if addr.strip()]

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(MAIL_FROM, recipients, message.as_string())
    except Exception:
        logger.error("Failed to send notification email", exc_info=True)
        return

    logger.info("Notification email sent to %s (%d products)", mail_to, len(products))

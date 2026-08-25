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


def _send_email(subject: str, text_body: str, html_body: str, mail_to: str) -> bool:
    """Send one email. Returns True on success, False on any failure/no-op."""
    if not (SMTP_USER and SMTP_PASSWORD and mail_to):
        logger.warning(
            "SMTP not configured (SMTP_USER/SMTP_PASSWORD/mail_to); "
            "skipping email notification"
        )
        return False

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = MAIL_FROM
    message["To"] = mail_to

    message.attach(MIMEText(text_body, "plain", "utf-8"))
    message.attach(MIMEText(html_body, "html", "utf-8"))

    recipients = [addr.strip() for addr in mail_to.split(",") if addr.strip()]

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(MAIL_FROM, recipients, message.as_string())
    except Exception:
        logger.error("Failed to send email", exc_info=True)
        return False

    return True


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

    subject = _build_subject(products, subject_prefix)
    text_body = _build_text_body(products)
    html_body = _build_html_body(products)

    if _send_email(subject, text_body, html_body, mail_to):
        logger.info("Notification email sent to %s (%d products)", mail_to, len(products))


def send_update_detected_email(
    site_url: str,
    previous_pages: int | None,
    total_pages: int,
    mail_to: str = MAIL_TO,
    subject_prefix: str = "[JD Monitor]",
) -> None:
    """Send a quick heads-up the moment a catalog change is detected.

    Sent before the (slow) full scrape / AI estimation / notify pipeline
    runs, so the user can go check time-sensitive items (e.g. kits that
    sell out fast) themselves instead of waiting minutes for the full
    "注目商品" email. No-op (logged, not raised) if SMTP is not
    configured.
    """
    subject = f"{subject_prefix} 更新を検知 - 注目商品を判定中..."

    was_text = str(previous_pages) if previous_pages is not None else "unknown"

    text_body = (
        f"ページ数が {was_text} -> {total_pages} に変化しました。\n\n"
        "これから注目商品の判定(AI査定・メルカリ相場取得)を行います。"
        "数分かかることがあるため、急ぎの場合は先にサイトを直接確認してください。\n\n"
        f"{site_url}"
    )
    html_body = (
        "<html><body>"
        f"<p>ページ数が {was_text} &rarr; {total_pages} に変化しました。</p>"
        "<p>これから注目商品の判定(AI査定・メルカリ相場取得)を行います。"
        "数分かかることがあるため、急ぎの場合は先にサイトを直接確認してください。</p>"
        f'<p><a href="{html.escape(site_url)}">{html.escape(site_url)}</a></p>'
        "</body></html>"
    )

    if _send_email(subject, text_body, html_body, mail_to):
        logger.info("Update-detected email sent to %s", mail_to)

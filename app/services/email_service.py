from dataclasses import dataclass
from email.message import EmailMessage
import re
import socket
import smtplib

from flask import current_app


@dataclass(slots=True)
class EmailSendResult:
    sent: bool
    warning_message: str | None = None


def _looks_like_email(value: str | None) -> bool:
    if not value:
        return False
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value.strip()) is not None


def _vendor_notification_email(vendor) -> str | None:
    recipient = (vendor.contact_email or "").strip()
    if _looks_like_email(recipient):
        return recipient

    owner_user = getattr(vendor, "owner_user", None)
    owner_email = (owner_user.email or "").strip() if owner_user and owner_user.email else ""
    if _looks_like_email(owner_email):
        return owner_email

    return None


def _smtp_sender() -> str | None:
    from_email = (current_app.config.get("MAIL_DEFAULT_SENDER") or "").strip()
    if not _looks_like_email(from_email):
        return None

    return from_email


def _subscription_email_text(vendor, user) -> str:
    subscriber_name = (getattr(user, "name", None) or "Unknown subscriber").strip()
    subscriber_email = (getattr(user, "email", None) or "Unknown email").strip()
    vendor_name = (getattr(vendor, "name", None) or "Vendor").strip()

    return "\n".join(
        [
            f"Hello {vendor_name},",
            "",
            "A new user has subscribed to your vendor on NutriSnap.",
            "",
            f"Subscriber name: {subscriber_name}",
            f"Subscriber email: {subscriber_email}",
            f"Vendor name: {vendor_name}",
            "",
            "Please log in to NutriSnap to view your vendor dashboard for more details.",
        ]
    )


def _smtp_candidates(server: str, port: int, use_tls: bool) -> list[dict[str, object]]:
    candidates = [{"server": server, "port": port, "use_tls": use_tls, "use_ssl": False}]

    # Gmail commonly works on 587 with STARTTLS or 465 with implicit SSL.
    if server.lower() == "smtp.gmail.com":
        if port == 587 and use_tls:
            candidates.append({"server": server, "port": 465, "use_tls": False, "use_ssl": True})
        elif port == 465:
            candidates[0]["use_ssl"] = True
            candidates[0]["use_tls"] = False

    return candidates


def _send_message_via_smtp(
    *,
    server: str,
    port: int,
    username: str,
    password: str,
    use_tls: bool,
    use_ssl: bool,
    message: EmailMessage,
) -> None:
    smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_class(server, port, timeout=15) as smtp:
        smtp.ehlo()
        if use_tls and not use_ssl:
            smtp.starttls()
            smtp.ehlo()
        smtp.login(username, password)
        smtp.send_message(message)


def send_vendor_subscription_email(vendor, user) -> EmailSendResult:
    recipient = _vendor_notification_email(vendor)
    smtp_server = (current_app.config.get("MAIL_SERVER") or "").strip()
    smtp_username = (current_app.config.get("MAIL_USERNAME") or "").strip()
    smtp_password = current_app.config.get("MAIL_PASSWORD") or ""
    smtp_port = current_app.config.get("MAIL_PORT")
    use_tls = bool(current_app.config.get("MAIL_USE_TLS"))
    sender = _smtp_sender()

    if not recipient:
        current_app.logger.warning(
            "Vendor subscription email skipped for vendor %s because no valid vendor email was found.",
            vendor.id,
        )
        return EmailSendResult(
            sent=False,
            warning_message="the vendor notification email could not be sent because the vendor email is invalid or missing.",
        )

    if not smtp_server or not smtp_port or not smtp_username or not smtp_password or not sender:
        current_app.logger.warning(
            "Vendor subscription email skipped for vendor %s because SMTP configuration is incomplete.",
            vendor.id,
        )
        return EmailSendResult(
            sent=False,
            warning_message="the vendor notification email could not be sent because email is not configured.",
        )

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = f"New subscriber for {vendor.name}"
    message.set_content(_subscription_email_text(vendor, user))

    smtp_candidates = _smtp_candidates(smtp_server, int(smtp_port), use_tls)
    last_timeout: Exception | None = None
    last_error: Exception | None = None

    for candidate in smtp_candidates:
        candidate_server = str(candidate["server"])
        candidate_port = int(candidate["port"])
        candidate_use_tls = bool(candidate["use_tls"])
        candidate_use_ssl = bool(candidate["use_ssl"])

        try:
            _send_message_via_smtp(
                server=candidate_server,
                port=candidate_port,
                username=smtp_username,
                password=smtp_password,
                use_tls=candidate_use_tls,
                use_ssl=candidate_use_ssl,
                message=message,
            )
            return EmailSendResult(sent=True)
        except smtplib.SMTPAuthenticationError as exc:
            current_app.logger.exception(
                "SMTP authentication failed for vendor %s to %s using %s:%s: %s",
                vendor.id,
                recipient,
                candidate_server,
                candidate_port,
                exc,
            )
            return EmailSendResult(
                sent=False,
                warning_message="the vendor notification email could not be sent because the email login was rejected.",
            )
        except smtplib.SMTPRecipientsRefused as exc:
            current_app.logger.exception(
                "SMTP rejected recipient for vendor %s to %s using %s:%s: %s",
                vendor.id,
                recipient,
                candidate_server,
                candidate_port,
                exc,
            )
            return EmailSendResult(
                sent=False,
                warning_message="the vendor notification email could not be sent because the vendor email address was rejected.",
            )
        except socket.timeout as exc:
            last_timeout = exc
            current_app.logger.warning(
                "SMTP connection timed out for vendor %s to %s using %s:%s.",
                vendor.id,
                recipient,
                candidate_server,
                candidate_port,
            )
        except (smtplib.SMTPException, OSError, ValueError) as exc:
            last_error = exc
            current_app.logger.warning(
                "SMTP delivery attempt failed for vendor %s to %s using %s:%s: %s",
                vendor.id,
                recipient,
                candidate_server,
                candidate_port,
                exc,
            )

    if last_timeout is not None:
        current_app.logger.exception(
            "All SMTP connection attempts timed out for vendor %s to %s using server %s.",
            vendor.id,
            recipient,
            smtp_server,
            exc_info=last_timeout,
        )
        return EmailSendResult(
            sent=False,
            warning_message="the vendor notification email could not be sent because the SMTP server could not be reached.",
        )

    if last_error is not None:
        current_app.logger.exception(
            "All SMTP delivery attempts failed for vendor %s to %s using server %s.",
            vendor.id,
            recipient,
            smtp_server,
            exc_info=last_error,
        )
        return EmailSendResult(
            sent=False,
            warning_message="the vendor notification email could not be sent due to an email delivery problem.",
        )

    return EmailSendResult(
        sent=False,
        warning_message="the vendor notification email could not be sent due to an email delivery problem.",
    )

import smtplib
from email.message import EmailMessage

from flask import current_app


def _is_truthy(value) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def send_vendor_subscription_email(vendor, subscriber) -> bool:
    mail_server = current_app.config.get("MAIL_SERVER")
    recipient = (vendor.contact_email or "").strip()
    sender = (
        current_app.config.get("MAIL_DEFAULT_SENDER")
        or current_app.config.get("MAIL_USERNAME")
        or ""
    ).strip()

    if not mail_server or not recipient or not sender:
        current_app.logger.info(
            "Skipping vendor subscription email for vendor_id=%s because mail is not configured.",
            getattr(vendor, "id", None),
        )
        return False

    message = EmailMessage()
    message["Subject"] = f"New NutriSnap subscriber for {vendor.name}"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        "\n".join(
            [
                f"Hello {vendor.name},",
                "",
                f"{subscriber.name} ({subscriber.email}) just subscribed to your vendor page on NutriSnap.",
                "They can now keep track of your menu updates from their account.",
                "",
                "This is an automated notification from NutriSnap.",
            ]
        )
    )

    port = int(current_app.config.get("MAIL_PORT") or 587)
    username = current_app.config.get("MAIL_USERNAME")
    password = current_app.config.get("MAIL_PASSWORD")
    use_ssl = _is_truthy(current_app.config.get("MAIL_USE_SSL"))
    use_tls = _is_truthy(current_app.config.get("MAIL_USE_TLS", True))

    if use_ssl:
        with smtplib.SMTP_SSL(mail_server, port, timeout=15) as smtp:
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)
        return True

    with smtplib.SMTP(mail_server, port, timeout=15) as smtp:
        smtp.ehlo()
        if use_tls:
            smtp.starttls()
            smtp.ehlo()
        if username and password:
            smtp.login(username, password)
        smtp.send_message(message)
    return True

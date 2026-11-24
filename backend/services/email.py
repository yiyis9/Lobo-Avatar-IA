import os
import smtplib
from email.message import EmailMessage
from mimetypes import guess_type


def is_email_configured() -> bool:
    return all(
        os.getenv(name, "").strip()
        for name in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD")
    )


def send_password_reset_code(recipient: str, code: str) -> None:
    host = os.environ["SMTP_HOST"].strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.environ["SMTP_USER"].strip()
    password = os.environ["SMTP_PASSWORD"].replace(" ", "")
    sender = os.getenv("SMTP_FROM", "").strip() or username
    use_starttls = os.getenv("SMTP_STARTTLS", "true").strip().lower() in {"1", "true", "yes", "on"}

    message = EmailMessage()
    message["Subject"] = "Código para restablecer tu contraseña | Lobo UPVT"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        "Hola,\n\n"
        f"Tu código para restablecer la contraseña de Lobo UPVT es: {code}\n\n"
        "El código vence en 10 minutos y solo se puede usar una vez. "
        "Si no solicitaste este cambio, ignora este correo.\n\n"
        "Universidad Politécnica del Valle de Toluca"
    )

    with smtplib.SMTP(host, port, timeout=15) as server:
        server.ehlo()
        if use_starttls:
            server.starttls()
            server.ehlo()
        server.login(username, password)
        server.send_message(message)


def send_contact_reply(
    recipient: str,
    subject: str,
    body: str,
    attachments: list[tuple[str, bytes]] | None = None,
) -> None:
    host = os.environ["SMTP_HOST"].strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.environ["SMTP_USER"].strip()
    password = os.environ["SMTP_PASSWORD"].replace(" ", "")
    sender = os.getenv("SMTP_FROM", "").strip() or username
    use_starttls = os.getenv("SMTP_STARTTLS", "true").strip().lower() in {"1", "true", "yes", "on"}

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message.set_content(body)
    for filename, content in attachments or []:
        safe_name = os.path.basename(filename.replace("\\", "/"))
        content_type = guess_type(safe_name)[0] or "application/octet-stream"
        maintype, subtype = content_type.split("/", 1)
        message.add_attachment(content, maintype=maintype, subtype=subtype, filename=safe_name)

    with smtplib.SMTP(host, port, timeout=20) as server:
        server.ehlo()
        if use_starttls:
            server.starttls()
            server.ehlo()
        server.login(username, password)
        server.send_message(message)

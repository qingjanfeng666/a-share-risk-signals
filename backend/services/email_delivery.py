"""Send registration codes through a configured SMTP account."""

import smtplib
import ssl
from email.message import EmailMessage

from backend.config import (
    SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_SECURITY, SMTP_USERNAME,
)


def is_configured():
    return all((SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM)) and SMTP_SECURITY in {"ssl", "starttls"}


def send_verification_code(email, code):
    if not is_configured():
        raise RuntimeError("邮件服务尚未配置。")
    message = EmailMessage()
    message["Subject"] = "A 股风险信号舱：注册验证码"
    message["From"] = SMTP_FROM
    message["To"] = email
    message.set_content(f"你的注册验证码是：{code}\n\n10 分钟内有效，使用一次后失效。若非本人操作，请忽略此邮件。")

    context = ssl.create_default_context()
    if SMTP_SECURITY == "ssl":
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10, context=context) as client:
            client.login(SMTP_USERNAME, SMTP_PASSWORD)
            client.send_message(message)
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as client:
            client.starttls(context=context)
            client.login(SMTP_USERNAME, SMTP_PASSWORD)
            client.send_message(message)

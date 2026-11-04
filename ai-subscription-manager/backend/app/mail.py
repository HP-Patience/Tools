import smtplib, ssl
from email.message import EmailMessage
from email.utils import formatdate
from html import escape


class MailNotConfigured(Exception):
    pass


def send_digest(settings, batch):
    if not settings.mail_ready:
        raise MailNotConfigured()
    msg = EmailMessage()
    msg["Subject"] = "[续订] 客户续费提醒 · " + str(len(batch["items"])) + " 项服务"
    msg["From"] = settings.smtp_from
    msg["To"] = batch["recipient"]
    msg["Date"] = formatdate(localtime=False)
    message_id = "<" + batch["id"] + "@subscription-desk.local>"
    msg["Message-ID"] = message_id
    lines = [
        "客户续费提醒",
        "统计时间：" + batch["as_of"],
        "请核对客户当前状态后联系续费。",
        "",
    ]
    for item in batch["items"]:
        lines.append(
            f"{item['customer_name']} · {item['product_name']} · {item['identifier'] or '未设置标识'}"
        )
        lines.append(
            "到期日期："
            + item["expires_on"]
            + " / 提醒节点："
            + item["kind"]
            + " / 原计划："
            + item["planned_on"]
        )
        lines.extend(c["kind"] + "：" + c["value"] for c in item["contacts"])
        lines.append(settings.app_url.rstrip("/") + "/services/" + str(item["service_id"]))
        lines.append("")
    body = "\n".join(lines)
    msg.set_content(body)
    msg.add_alternative(
        '<html><body><pre style="font-family:sans-serif;white-space:pre-wrap">'
        + escape(body)
        + "</pre></body></html>",
        subtype="html",
    )
    smtp_class = smtplib.SMTP_SSL if settings.smtp_ssl else smtplib.SMTP
    kwargs = {"context": ssl.create_default_context()} if settings.smtp_ssl else {}
    with smtp_class(settings.smtp_host, settings.smtp_port, timeout=10, **kwargs) as server:
        if settings.smtp_starttls and not settings.smtp_ssl:
            server.starttls(context=ssl.create_default_context())
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(msg)
    return message_id

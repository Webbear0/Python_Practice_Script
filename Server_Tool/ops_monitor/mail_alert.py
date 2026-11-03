# mail_alert.py -- 邮件告警模块 (smtplib SSL, 465 端口)
import smtplib
from email.mime.text import MIMEText

# ── 邮箱配置 (请根据实际情况修改, 留空则跳过发送) ──
SMTP_HOST = ""
SMTP_PORT = 465
SMTP_USER = ""          # 发件人邮箱地址
SMTP_PASS = ""          # 邮箱 SMTP 授权码
ALERT_TO  = ""          # 收件人邮箱地址


def send_alert(subject, body):
    """通过 SMTP SSL 发送告警邮件, 未配置或发送失败时仅打印提示, 不中断主流程。"""
    if not all([SMTP_USER, SMTP_PASS, ALERT_TO]):
        print(f"    [邮件] 未配置邮箱, 跳过告警: {subject}")
        return
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"]    = SMTP_USER
        msg["To"]      = ALERT_TO
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.sendmail(SMTP_USER, [ALERT_TO], msg.as_string())
        print(f"    [邮件] 告警已发送: {subject}")
    except Exception as e:
        print(f"    [邮件] 发送失败: {e}")

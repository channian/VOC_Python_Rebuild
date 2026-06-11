"""
notify_service.py — 異常通知發送

通知管道決策（2026-06-11 與用戶確認）：
  Email (SMTP)  — ✅ 唯一啟用的管道
  SMS (CHT)     — ❌ 已停用，程式碼已移除（舊版 SendSMS.cs 不移植）
  PushPlus 推播 — ❌ 暫不實作，日後有需要再新增（舊版 CallPushPlus）
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from fastapi import BackgroundTasks
from config import settings

logger = logging.getLogger(__name__)

SMTP_SERVER = "10.12.10.31"  # mapped from SmtpMessage.cs


def send_email_sync(subject: str, body: str, to_addresses: list[str]):
    """ 透過 IT mail server 發送 Email """
    # --- 測試模式攔截邏輯 ---
    if settings.TEST_MODE:
        logger.info(f"TEST_MODE 攔截 Email。原標題: {subject}, 原收件: {to_addresses}")
        subject = f"[TEST MODE 攔截] {subject}"
        body = f"<div style='background-color:#ffe4e6; padding:10px; border-radius:5px; margin-bottom:15px; border: 1px solid #f43f5e; color: #9f1239;'><b>(測試攔截) 原本這封信會寄給：{to_addresses}</b></div>" + body
        to_addresses = [settings.TEST_DEV_EMAIL]
    # -----------------------

    try:
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = "VOC_System@asegroup.com"
        msg['To'] = ",".join(to_addresses)
        msg.attach(MIMEText(body, 'html', 'utf-8'))

        with smtplib.SMTP(SMTP_SERVER) as server:
            server.send_message(msg)
        logger.info(f"Email sent successfully to {to_addresses}")
    except Exception as e:
        logger.error(f"Error sending email to {to_addresses}: {e}")


def add_notification_task(background_tasks: BackgroundTasks, subject: str, message: str, emails: list[str] = None):
    """
    綁定到 FastAPI 的 BackgroundTasks，不卡住使用者送出表單的連線。
    """
    if emails:
        background_tasks.add_task(send_email_sync, subject, message, emails)

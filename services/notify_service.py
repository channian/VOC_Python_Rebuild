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
SMTP_TIMEOUT_SECONDS = 30    # 連線/讀寫逾時；None（smtplib 預設）會無限等待，見 send_email()


def send_email_sync(subject: str, body: str, to_addresses: list[str], cc_addresses: list[str] = None):
    """
    透過 IT mail server 發送 Email。
    cc_addresses：副本收件人（新增於異常派報 dispatch_service.run_dispatch 移植時，
    因舊版信件需要 TO/CC 分開，向下相容——不傳就等同原本行為）。
    """
    cc_addresses = list(cc_addresses or [])
    # --- 測試模式攔截邏輯 ---
    if settings.TEST_MODE:
        logger.info(f"TEST_MODE 攔截 Email。原標題: {subject}, 原收件: {to_addresses}, 原副本: {cc_addresses}")
        subject = f"[TEST MODE 攔截] {subject}"
        body = (f"<div style='background-color:#ffe4e6; padding:10px; border-radius:5px; margin-bottom:15px; "
                f"border: 1px solid #f43f5e; color: #9f1239;'><b>(測試攔截) 原本這封信會寄給：{to_addresses}"
                f"（副本：{cc_addresses}）</b></div>") + body
        to_addresses = [settings.TEST_DEV_EMAIL]
        cc_addresses = []
    # -----------------------

    # --- 測試用固定副本（ALWAYS_CC_EMAIL）：所有信一律 CC 到指定地址，方便確認信件有寄出 ---
    # 放在 TEST_MODE 攔截之後：真實寄送時把自己加進 CC；已在收件人清單中的地址不重複加。
    always_cc = getattr(settings, "ALWAYS_CC_EMAIL", "") or ""
    for addr in (a.strip() for a in always_cc.split(",")):
        if addr and addr not in to_addresses and addr not in cc_addresses:
            cc_addresses.append(addr)
    # -----------------------

    try:
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = "VOC_System@asegroup.com"
        msg['To'] = ",".join(to_addresses)
        if cc_addresses:
            msg['Cc'] = ",".join(cc_addresses)
        msg.attach(MIMEText(body, 'html', 'utf-8'))

        # timeout 不可省略：smtplib 預設是「無限等待」，SMTP 主機不可達時（例如在公司網路外
        # 測試、或防火牆擋掉）會卡在 socket.create_connection 永遠不返回，連 Ctrl+C 都難中斷，
        # 派報 worker 等於整個停擺且看不出原因（2026-08-02 實測確認）。
        # 30 秒對正常內網 SMTP 綽綽有餘，逾時會走下面的 except 記錄錯誤後繼續，不影響其他收件者。
        with smtplib.SMTP(SMTP_SERVER, timeout=SMTP_TIMEOUT_SECONDS) as server:
            server.send_message(msg)
        logger.info(f"Email sent successfully to {to_addresses} (cc={cc_addresses})")
    except Exception as e:
        logger.error(f"Error sending email to {to_addresses}: {e}")


def add_notification_task(background_tasks: BackgroundTasks, subject: str, message: str,
                          emails: list[str] = None, cc: list[str] = None):
    """
    綁定到 FastAPI 的 BackgroundTasks，不卡住使用者送出表單的連線。
    """
    if emails:
        background_tasks.add_task(send_email_sync, subject, message, emails, cc)

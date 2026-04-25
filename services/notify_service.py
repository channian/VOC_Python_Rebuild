import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from fastapi import BackgroundTasks

logger = logging.getLogger(__name__)

SMTP_SERVER = "10.12.10.31" # mapped from SmtpMessage.cs
SMS_IP = "203.66.172.133"
SMS_PORT = 8001
SMS_USER = "11307"
SMS_PWD = "11307"

def send_email_sync(subject: str, body: str, to_addresses: list[str]):
    """ 透過 IT mail server 發送 Email """
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

def send_sms_sync(phone: str, message: str):
    """ 
    透過 SNSCOMSERVER COM 元件發送簡訊 (從 SendSMS.cs 移植)
    若 Windows 環境未註冊該 COM 元件，將降級為 Logger 列印。
    """
    logger.info(f"Attempting to send SMS to {phone}...")
    try:
        import win32com.client
        m_sns = win32com.client.Dispatch("SNSCOMSERVER.SnsComObject")
        login_res = m_sns.Login(SMS_IP, SMS_PORT, SMS_USER, SMS_PWD)
        if login_res == 0:
            res = m_sns.SubmitMessage(phone, message)
            if res != 0:
                logger.error(f"SMS Submit Error: {m_sns.RespMessage}")
            else:
                logger.info("SMS sent success!")
        else:
            logger.error(f"SMS Login Error: {login_res}")
    except ImportError:
        logger.warning(f"pywin32 is not installed. Mock SMS Sending to {phone}: {message}")
    except BaseException as e:
        logger.warning(f"Fallback/Mock SMS sending (COM not available): {e} | To: {phone} msg: {message}")

def add_notification_task(background_tasks: BackgroundTasks, subject: str, message: str, emails: list[str] = None, phone: str = None):
    """
    綁定到 FastAPI 的 BackgroundTasks，不卡住使用者送出表單的連線。
    """
    if emails:
        background_tasks.add_task(send_email_sync, subject, message, emails)
    if phone:
        background_tasks.add_task(send_sms_sync, phone, message)

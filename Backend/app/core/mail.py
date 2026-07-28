import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from app.config import settings
from app.core.logging import logger
import os

def send_otp_email(to_email: str, otp: str):
    logger.info(f"Preparing to send OTP email to: {to_email}")
    try:
        # 1. Build MIME Message
        msg = MIMEMultipart('related')
        msg['From'] = settings.SMTP_FROM
        msg['To'] = to_email
        msg['Subject'] = "Civil Work Estimation - Registration Verification Code"
        
        # Plain text fallback body
        text_body = f"""Dear User,

Thank you for registering with Civil Work Estimation.

Your 6-digit verification code (OTP) is:

👉  {otp}  👈

This code is valid for 10 minutes. Please enter this code on the registration page to verify your email and activate your account.

Best regards,
Civil Work Estimation Team
"""

        # Minimalist professional HTML body
        html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="light dark">
  <meta name="supported-color-schemes" content="light dark">
  <title>Civil Work Estimation Verification</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      background-color: #ffffff;
      margin: 0;
      padding: 0;
      color: #000000;
    }}
    .wrapper {{
      width: 100%;
      background-color: #ffffff;
      padding: 40px 20px;
      box-sizing: border-box;
      text-align: center;
    }}
    .container {{
      max-width: 600px;
      margin: 0 auto;
      background-color: #ffffff;
      text-align: center;
    }}
    .logo-container {{
      margin-bottom: 30px;
      text-align: center;
    }}
    .logo-container img {{
      width: 140px;
      height: auto;
      display: inline-block;
    }}
    .logo-text {{
      font-size: 32px;
      font-weight: 800;
      color: #111827;
      margin-top: 10px;
      letter-spacing: -0.5px;
      text-align: center;
    }}
    h1 {{
      font-size: 24px;
      font-weight: 700;
      color: #111827;
      margin-top: 30px;
      margin-bottom: 30px;
      text-align: center;
    }}
    p {{
      font-size: 16px;
      line-height: 1.6;
      color: #374151;
      margin: 0 auto 20px auto;
      text-align: center;
      max-width: 500px;
    }}
    .otp-code {{
      font-family: 'Courier New', Courier, monospace;
      font-size: 36px;
      font-weight: 800;
      color: #000000;
      letter-spacing: 12px;
      margin: 30px 0;
      text-align: center;
    }}
    .footer {{
      margin-top: 50px;
      padding-top: 30px;
      border-top: 1px solid #e5e7eb;
      text-align: center;
    }}
    .footer-text {{
      font-size: 13px;
      color: #9ca3af;
      margin: 0 auto 10px auto;
      line-height: 1.5;
      text-align: center;
    }}
    
    /* Dark Mode Styles */
    @media (prefers-color-scheme: dark) {{
      body, .wrapper, .container {{
        background-color: #000000 !important;
        color: #ffffff !important;
      }}
      .logo-text, h1, .otp-code {{
        color: #ffffff !important;
      }}
      p {{
        color: #d1d5db !important;
      }}
      .footer {{
        border-top-color: #374151 !important;
      }}
      .footer-text {{
        color: #6b7280 !important;
      }}
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="container">
      
      <div class="logo-container">
        <center>
          <img src="cid:logo" alt="Logo" />
        </center>
        <div class="logo-text">Civil Work Estimation</div>
      </div>
      
      <h1>OTP Verification Email</h1>
      
      <p style="text-align: center;">Dear User,</p>
      
      <p style="text-align: center;">Thank you for registering with Civil Work Estimation. To complete your registration, please use the following OTP (One-Time Password) to verify your account:</p>
      
      <div class="otp-code">
        <center>{otp}</center>
      </div>
      
      <p style="text-align: center;">If you did not request this verification code, you can safely ignore this email. Someone may have entered your email address by mistake.</p>
      
      <p style="text-align: center; margin-bottom: 0;">Best regards,<br>The Civil Work Estimation Team</p>
      
      <div class="footer">
        <p class="footer-text">This is an automated security message from Civil Work Estimation.</p>
        <p class="footer-text">&copy; 2026 Civil Work Estimation. All rights reserved.</p>
      </div>
      
    </div>
  </div>
</body>
</html>
"""

        msg_alternative = MIMEMultipart('alternative')
        msg_alternative.attach(MIMEText(text_body, 'plain', 'utf-8'))
        msg_alternative.attach(MIMEText(html_body, 'html', 'utf-8'))
        msg.attach(msg_alternative)
        
        # Attach the circular Favicon
        icon_path = r"c:\Users\Hp\Desktop\Costmate\Frontend\src\app\icon.png"
        if os.path.exists(icon_path):
            with open(icon_path, 'rb') as f:
                img_data = f.read()
            image = MIMEImage(img_data, name=os.path.basename(icon_path))
            image.add_header('Content-ID', '<logo>')
            image.add_header('Content-Disposition', 'inline', filename=os.path.basename(icon_path))
            msg.attach(image)
        
        # 2. Establish secure SMTP connection
        logger.info(f"Connecting to SMTP server {settings.SMTP_HOST}:{settings.SMTP_PORT}...")
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
        
        if settings.SMTP_TLS:
            server.starttls()
            
        logger.info("Logging into SMTP server...")
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        
        logger.info("Sending email transmission...")
        server.sendmail(settings.SMTP_FROM, to_email, msg.as_string())
        
        server.quit()
        logger.info(f"OTP verification email successfully sent to {to_email}.")
        return True
    except Exception as e:
        logger.error(f"Failed to send SMTP email to {to_email}: {e}")
        raise e

#!/usr/bin/env python3
# 测试邮件发送功能

import os
import sys
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_email():
    """测试邮件发送功能，使用环境变量中的配置"""
    from dotenv import load_dotenv
    load_dotenv()
    
    smtp_server = os.getenv("SMTP_SERVER", "smtp.qq.com")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    email_to = os.getenv("EMAIL_TO")
    
    if not all([username, password, email_to]):
        print("❌ 请在 .env 文件中配置 SMTP_USERNAME, SMTP_PASSWORD, EMAIL_TO")
        return False
    
    print(f"SMTP服务器: {smtp_server}:{smtp_port}")
    print(f"发件人: {username}")
    print(f"收件人: {email_to}")
    print("开始测试邮件发送...")
    
    try:
        # 创建邮件
        msg = MIMEMultipart()
        msg['From'] = username
        msg['To'] = email_to
        msg['Subject'] = "ArXiv Paper Tracker - 测试邮件"
        
        body = "这是一封测试邮件，用于验证邮箱SMTP配置是否正确。"
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        if smtp_port == 465:
            # 使用SSL
            print("使用SSL连接...")
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, context=context)
        else:
            # 使用TLS
            print("使用TLS连接...")
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
            server.starttls()
        
        print("正在登录...")
        server.login(username, password)
        
        print("正在发送邮件...")
        server.sendmail(username, email_to, msg.as_string())
        server.quit()
        
        print("✅ 邮件发送成功!")
        return True
        
    except Exception as e:
        print(f"❌ 邮件发送失败: {e}")
        import traceback
        print(f"详细错误: {traceback.format_exc()}")
        return False


if __name__ == "__main__":
    test_email()

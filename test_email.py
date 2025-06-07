#!/usr/bin/env python3

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def test_qq_email():
    smtp_server = "smtp.qq.com"
    smtp_port = 465  # 或者 587
    username = "913928542@qq.com"
    password = "bhnufpnvfcdbbegb"
    
    print("开始测试QQ邮箱发送...")
    
    try:
        # 创建邮件
        msg = MIMEMultipart()
        msg['From'] = username
        msg['To'] = "pikel_ar5iv@outlook.com"
        msg['Subject'] = "QQ邮箱测试邮件"
        
        body = "这是一封测试邮件，用于验证QQ邮箱SMTP配置。"
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
        text = msg.as_string()
        server.sendmail(username, "pikel_ar5iv@outlook.com", text)
        server.quit()
        
        print("邮件发送成功!")
        
    except Exception as e:
        print(f"邮件发送失败: {e}")
        import traceback
        print(f"详细错误: {traceback.format_exc()}")

if __name__ == "__main__":
    test_qq_email()
# -*- coding: utf-8 -*-
import asyncio
import requests
import smtplib
from email.mime.text import MIMEText
from config import EMAIL_ADDRESS, EMAIL_PASSWORD, RECEIVER_EMAIL
from utils.logging_utils import log_to_file
from utils.console_utils import single_line_print

async def get_sol_price():
    """
    Güncel SOL/USD fiyatını asenkron olarak getirir
    
    Returns:
        float: SOL fiyatı veya None
    """
    try:
        for _ in range(3):  # En fazla 3 deneme
            try:
                response = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    lambda: requests.get(
                        "https://api.binance.com/api/v3/ticker/price?symbol=SOLUSDT", 
                        timeout=5
                    )
                )
                response.raise_for_status()
                data = response.json()
                return float(data['price'])
            except (requests.RequestException, ValueError, KeyError):
                await asyncio.sleep(1)
        
        # Alternatif API'ler denenebilir
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: requests.get(
                    "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd",
                    timeout=5
                )
            )
            response.raise_for_status()
            data = response.json()
            return float(data['solana']['usd'])
        except Exception:
            pass
            
        return None
    except Exception as e:
        log_to_file(f"SOL fiyatı alınamadı: {e}")
        return None

def send_email(subject, message):
    """
    E-posta gönderme fonksiyonu
    
    Args:
        subject (str): E-posta konusu
        message (str): E-posta içeriği
    """
    try:
        # E-posta sunucusu ayarları
        smtp_server = "smtp.gmail.com"
        smtp_port = 587  # TLS portu

        # E-posta oluşturma
        msg = MIMEText(message)
        msg['Subject'] = subject
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = RECEIVER_EMAIL

        # SMTP bağlantısı
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()  # TLS bağlantısı
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
        
        single_line_print("✅ E-posta gönderildi!")
    except Exception as e:
        single_line_print(f"❌ E-posta gönderme hatası: {e}")
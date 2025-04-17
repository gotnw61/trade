# -*- coding: utf-8 -*-
import os
import logging
import re
from datetime import datetime
from loguru import logger
import sys

from config import LOG_PATH

def setup_logging():
    """
    Emoji ve Unicode karakter sorunlarını çözmek ve fazla log mesajlarını 
    engellemek için iyileştirilmiş log ayarları.
    """
    import logging
    
    # Özel bir handler oluşturun
    class UnicodeHandler(logging.StreamHandler):
        def emit(self, record):
            try:
                msg = self.format(record)
                # Emojileri ASCII karakterler ile değiştirin
                msg = re.sub(r'[\U00010000-\U0010ffff\u2600-\u26FF\u2700-\u27BF]', "", msg)
                self.stream.write(msg + self.terminator)
                self.flush()
            except Exception:
                self.handleError(record)
    
    # Root logger'ı yapılandırın
    logger = logging.getLogger()
    logger.setLevel(logging.WARNING)  # INFO yerine WARNING seviyesine yükseltin
    
    # Tüm mevcut handler'ları kaldırın
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Yeni handler'ı ekleyin
    handler = UnicodeHandler(sys.stdout)
    formatter = logging.Formatter('%(message)s')  # Basitleştirilmiş formatter
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Dosya handler'ı ekleyin
    file_handler = logging.FileHandler(os.path.join(LOG_PATH, "tradebot.log"), encoding="utf-8")
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)
    
    # logging modülünün kapsamlı debug mesajlarını da kapatın
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("solana").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

def log_to_file(message, log_file="tradebot_log.txt"):
    """
    Logs messages to a specified file in the log directory.
    
    Args:
        message (str): Message to be logged
        log_file (str, optional): Name of the log file. Defaults to "tradebot_log.txt"
    """
    try:
        # Ensure log directory exists
        if not os.path.exists(LOG_PATH):
            os.makedirs(LOG_PATH)
        
        # Full path to the log file
        full_path = os.path.join(LOG_PATH, log_file)
        
        # Emojileri filtreleyin (opsiyonel)
        filtered_message = re.sub(r'[\U00010000-\U0010ffff\u2600-\u26FF\u2700-\u27BF]', "", message)
        
        # Write log message with timestamp
        with open(full_path, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {filtered_message}\n")
    except Exception as e:
        print(f"Log dosyasına yazma hatası: {e}")

def trade_log(message, mint_address=None, log_file=None):
    """
    Ticaret günlüğü için özel log fonksiyonu
    
    Args:
        message (str): Log mesajı
        mint_address (str, optional): Token mint adresi
        log_file (str, optional): Log dosyası adı
    """
    try:
        # Gereksiz bilgileri filtrele
        if message and (
            message.startswith("🔍 Durum:") or
            "Token Alım Kontrolleri:" in message or
            "Otomatik Alım Durumu:" in message or
            "Mevcut Pozisyon Sayısı:" in message or
            "Maksimum Pozisyon Sınırı:" in message or
            "Token Bilgileri:" in message or
            "Likidite:" in message or
            "Fiyat:" in message or
            "WebSocket zaman aşımı" in message or
            "Jupiter mantıksız fiyat" in message or
            "Jupiter API fallback hatası" in message or
            "Token izlemeye ekleniyor" in message or
            "zaten izleniyor" in message or
            "DexScreener" in message or
            "GUI Güncellemesi:" in message or
            "Fiyat Güncellendi:" in message
        ):
            return
            
        from utils.console_utils import single_line_print
        
        # Tek satırda güncelleme (aynı satırda güncelleme) için \r karakteri kontrolü
        is_inline_update = message.startswith("\r")
        if is_inline_update:
            # \r karakterini kaldır
            message = message[1:]
            # Konsolda aynı satırı güncelle
            single_line_print(f"\r{message}", end="")
        else:
            # Normal log yazdırma
            single_line_print(message)
            
        # Log dosyası adını belirle
        if log_file is None:
            log_file = f"{mint_address}_trade_log.txt" if mint_address else "trade_log.txt"
        
        # Log dosyasına kaydet
        log_to_file(message, log_file)
        
    except Exception as e:
        print(f"Ticaret log hatası: {e}")
# -*- coding: utf-8 -*-
import os
import platform
import subprocess
import sys
from colorama import init, Fore, Style

# Colorama'yı başlat
init(autoreset=True)

def single_line_print(message, end="\n"):
    """
    Tek satırda güncelleme yapabilen print fonksiyonu
    
    Args:
        message (str): Gösterilecek mesaj
        end (str): Satır sonu karakteri
    """
    # ANSI escape sequence kullanarak imleci satır başına taşı ve satırı temizle
    if sys.stdout.isatty():  # Terminal kontrolü
        print(f"\033[2K\r{message}", end=end, flush=True)
    else:
        print(message, end=end, flush=True)

def animated_text(message, color=None):
    """
    Renkli konsol çıktısı
    
    Args:
        message (str): Gösterilecek mesaj
        color (str, optional): Metin rengi
    """
    if color:
        single_line_print(f"{color}{message}{Style.RESET_ALL}")
    else:
        single_line_print(message)

def clear_screen():
    """
    Platform bağımsız ekran temizleme fonksiyonu
    """
    system = platform.system().lower()
    if system == 'windows':
        subprocess.call('cls', shell=True)
    else:
        subprocess.call('clear', shell=True)

def clear_console_keep_wallet_info(wallet, balance, sol_price):
    """
    Konsolu temizler ve sadece cüzdan bilgilerini gösterir.
    10 dakikada bir otomatik çalıştırılır.
    """
    clear_screen()
    single_line_print(f"\033[36m===== GOTNW TradeBot Cüzdan Bilgileri =====\033[0m")
    single_line_print(f"\033[32mCüzdan Adresi:\033[0m {wallet}")
    single_line_print(f"\033[32mSOL Bakiye:\033[0m {balance:.4f}")
    single_line_print(f"\033[32mSOL/USD Fiyatı:\033[0m ${sol_price:.2f}")
    single_line_print(f"\033[32mToplam Değer:\033[0m ${balance * sol_price:.2f}")
    single_line_print(f"\033[36m==========================================\033[0m")

def check_night_mode_transition():
    """
    Gece modu geçişini kontrol eder ve log kaydı düşer
    """
    from gotnw_tradebot.utils.logging_utils import log_to_file
    from gotnw_tradebot.utils.trade_utils import is_night_mode
    
    try:
        if is_night_mode():
            log_to_file("Gece modu etkin")
            animated_text("Gece modu etkin")
        else:
            log_to_file("Gece modu devre dışı")
            animated_text("Gece modu devre dışı")
    except Exception as e:
        log_to_file(f"Gece modu kontrol hatası: {e}")
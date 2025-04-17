# -*- coding: utf-8 -*-
from datetime import datetime, timezone
import csv
import numpy as np
from config import trade_settings

def is_night_mode():
    """
    Gece modunun aktif olup olmadığını kontrol eder
    
    Returns:
        bool: Gece modu etkin ise True, değil ise False
    """
    if not trade_settings.get("night_mode_enabled", False):
        return False
    
    try:
        now = datetime.now().time()
        start_time = datetime.strptime(trade_settings.get("night_mode_start", "00:00"), "%H:%M").time()
        end_time = datetime.strptime(trade_settings.get("night_mode_end", "08:00"), "%H:%M").time()
        
        # Gece modu aynı günde
        if start_time < end_time:
            return start_time <= now <= end_time
        # Gece modu gece yarısını geçiyorsa
        else:
            return now >= start_time or now <= end_time
    except Exception as e:
        from utils.logging_utils import log_to_file
        log_to_file(f"Gece modu kontrolü hatası: {e}")
        return False

def check_trading_hours():
    """
    Şu anki zamanın işlem yapmak için uygun olup olmadığını kontrol eder.
    ABD piyasa saatlerine göre filtreleme yapar.
    """
    now = datetime.now(timezone.utc)
    
    # UTC saat dilimine göre ABD piyasa saatleri
    # New York Borsası açılış (UTC 14:30) ve kapanış (UTC 21:00)
    
    # Hangi gün olduğunu kontrol et (0 = Pazartesi, 6 = Pazar)
    day_of_week = now.weekday()
    
    # Hafta sonu kontrolü (Cumartesi ve Pazar)
    if day_of_week >= 5:  # 5 = Cumartesi, 6 = Pazar
        return {
            "is_suitable_time": False,
            "reason": "Hafta sonu - piyasa kapalı",
            "risk_level": "medium",
            "suggestion": "Normal işlem limitleri kullanılabilir"
        }
    
    # Saat kontrolü
    hour = now.hour
    minute = now.minute
    current_minutes = hour * 60 + minute  # Günün dakikası
    
    ny_open_minutes = 14 * 60 + 30  # 14:30 UTC (New York Borsası açılış)
    ny_close_minutes = 21 * 60  # 21:00 UTC (New York Borsası kapanış)
    
    # New York açılışı öncesi 30 dakika ve sonrası 30 dakika
    is_ny_opening = ny_open_minutes - 30 <= current_minutes <= ny_open_minutes + 30
    
    # Volatil saatlerde mi?
    is_volatile_hours = is_ny_opening
    
    # Normal işlem saatleri mi?
    is_trading_hours = ny_open_minutes <= current_minutes <= ny_close_minutes
    
    # Sonuçları döndür
    if is_volatile_hours:
        return {
            "is_suitable_time": True,
            "reason": "Piyasa açılış/kapanış saatleri - yüksek volatilite",
            "risk_level": "high",
            "suggestion": "Pozisyon boyutunu %50 azalt ve daha sıkı stop-loss kullan"
        }
    elif is_trading_hours:
        return {
            "is_suitable_time": True,
            "reason": "Normal işlem saatleri",
            "risk_level": "low",
            "suggestion": "Normal işlem limitleri kullanılabilir"
        }
    else:
        return {
            "is_suitable_time": True,
            "reason": "Düşük likidite saatleri",
            "risk_level": "medium",
            "suggestion": "Pozisyon boyutunu %25 azalt"
        }

def generate_trade_analysis(trades):
    """
    Ticaret verilerinden detaylı analiz oluşturur
    
    Args:
        trades (list): İşlem geçmişi listesi
    
    Returns:
        dict: Detaylı ticaret analizi
    """
    if not trades:
        return {
            "total_trades": 0,
            "profitable_trades": 0,
            "total_profit": 0,
            "avg_profit": 0,
            "avg_loss": 0,
            "success_rate": 0
        }
    
    # Toplam ve karlı işlem sayısı
    total_trades = len(trades)
    profitable_trades = sum(1 for trade in trades if trade.get('profit_loss', 0) > 0)
    
    # Kâr/zarar hesaplamaları
    total_profit = sum(t.get('profit_loss', 0) for t in trades)
    
    # Karlı ve zararlı işlemler
    profits = [trade.get('profit_loss', 0) for trade in trades if trade.get('profit_loss', 0) > 0]
    losses = [trade.get('profit_loss', 0) for trade in trades if trade.get('profit_loss', 0) < 0]
    
    # Ortalama kâr ve zarar
    avg_profit = sum(profits) / len(profits) if profits else 0
    avg_loss = sum(losses) / len(losses) if losses else 0
    
    # Başarı oranı
    success_rate = (profitable_trades / total_trades) * 100 if total_trades > 0 else 0
    
    return {
        "total_trades": total_trades,
        "profitable_trades": profitable_trades,
        "total_profit": total_profit,
        "avg_profit": avg_profit,
        "avg_loss": avg_loss,
        "success_rate": success_rate
    }

def create_daily_report(trades, filename=None):
    """
    Günlük ticaret raporunu oluşturur
    
    Args:
        trades (list): İşlem geçmişi listesi
        filename (str, optional): Rapor dosya adı
    
    Returns:
        str: Rapor içeriği
    """
    # Analiz sonuçlarını al
    analysis = generate_trade_analysis(trades)
    
    # Rapor içeriğini oluştur
    report = "GOTNW TradeBot - Günlük Ticaret Raporu\n"
    report += f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    report += f"Toplam İşlem Sayısı: {analysis['total_trades']}\n"
    report += f"Karlı İşlemler: {analysis['profitable_trades']} (%{analysis['success_rate']:.2f})\n"
    report += f"Toplam Kâr/Zarar: {analysis['total_profit']:.4f} SOL\n"
    report += f"Ortalama Kâr: {analysis['avg_profit']:.4f} SOL\n"
    report += f"Ortalama Zarar: {analysis['avg_loss']:.4f} SOL\n\n"
    
    # Detaylı işlem listesi
    report += "İşlem Detayları:\n"
    for trade in trades:
        report += (f"- {trade.get('type', 'İşlem').upper()} | "
                   f"{trade.get('symbol', 'Bilinmeyen')} | "
                   f"Miktar: {trade.get('amount', 0):.4f} SOL | "
                   f"Kâr/Zarar: {trade.get('profit_loss', 0):.4f} SOL\n")
    
    # Dosyaya yazma (isteğe bağlı)
    if filename:
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                f.write(report)
            from utils.console_utils import single_line_print
            single_line_print(f"Rapor dosyası oluşturuldu: {filename}")
        except Exception as e:
            from utils.logging_utils import log_to_file
            log_to_file(f"Rapor dosyası oluşturma hatası: {e}")
    
    return report

def export_trade_history(trades, filepath):
    """
    İşlem geçmişini CSV dosyasına aktarır
    
    Args:
        trades (list): İşlem geçmişi listesi
        filepath (str): Dışa aktarma dosya yolu
    
    Returns:
        bool: Başarı durumu
    """
    try:
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Tarih", "İşlem Türü", "Mint Adresi", "Token", "Fiyat", "Miktar", "Kâr/Zarar"])

            for trade in trades:
                timestamp = trade.get("timestamp")
                if isinstance(timestamp, datetime):
                    date_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    date_str = str(timestamp)

                trade_type = "Alım" if trade.get("buy_price", 0) < trade.get("sell_price", 0) else "Satım"
                mint_address = trade.get("mint", "")
                symbol = trade.get("symbol", "Bilinmeyen")
                price = trade.get("sell_price", 0)
                amount = trade.get("amount", 0)
                profit_loss = trade.get("profit_loss", 0)

                writer.writerow([date_str, trade_type, mint_address, symbol, price, amount, profit_loss])
        
        from utils.logging_utils import log_to_file
        log_to_file(f"İşlem geçmişi dışa aktarıldı: {filepath}")
        return True
    except Exception as e:
        from utils.logging_utils import log_to_file
        log_to_file(f"İşlem geçmişi dışa aktarma hatası: {e}")
        return False
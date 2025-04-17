# -*- coding: utf-8 -*-
"""
İşlem penceresi yönetimi modülü
"""

import tkinter as tk
from tkinter import scrolledtext, ttk
from datetime import datetime

from loguru import logger

from utils.logging_utils import log_to_file
from utils.formatting import format_price
from config import trade_settings, open_windows

def open_trade_window(trade_bot, mint_address, trade_type, initial_content):
    """
    Thread-safe işlem penceresi açar
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address: Token mint adresi
        trade_type: İşlem tipi (Alım/Satım)
        initial_content: Başlangıç içeriği
    
    Returns:
        tuple: (pencere, log fonksiyonu)
    """
    if mint_address in trade_bot.trade_windows:
        return None, trade_bot.trade_windows[mint_address]
    
    def create_window():
        try:
            trade_window = tk.Toplevel(trade_bot.root)
            trade_window.title(f"{trade_type} - {mint_address}")
            trade_window.geometry("600x400")
            trade_window.protocol("WM_DELETE_WINDOW", lambda: close_trade_window(trade_bot, mint_address))
            
            # open_windows'a ekleme yapmadan önce güvenlik kontrolü
            if not isinstance(open_windows, dict):
                open_windows = {}  # Set'i dictionary'e dönüştürme güvenlik kontrolü
            
            open_windows[mint_address] = trade_window
            
            # Log alanı
            log_area = scrolledtext.ScrolledText(trade_window, height=10, width=70, wrap=tk.WORD)
            log_area.pack(pady=5, padx=5, fill=tk.BOTH, expand=True)
            log_area.insert(tk.END, initial_content + "\n")
            log_area.config(state='disabled')
            
            # Bilgi frame'i
            info_frame = ttk.Frame(trade_window)
            info_frame.pack(pady=5, padx=5, fill=tk.X)
            
            # Renk ayarları
            text_color = "#000000" if not trade_settings["night_mode_enabled"] else "#FFFFFF"
            profit_color = "#008000"  # Yeşil
            loss_color = "#FF0000"    # Kırmızı
            bg_color = "#FFFFFF" if not trade_settings["night_mode_enabled"] else "#2B2B2B"
            
            trade_window.configure(bg=bg_color)
            info_frame.configure(style="Custom.TFrame")
            
            # Stil ayarları
            style = ttk.Style()
            style.configure("Custom.TFrame", background=bg_color)
            style.configure("Custom.TLabel", background=bg_color, foreground=text_color)
            style.configure("Custom.TProgressbar", background=profit_color, troughcolor=bg_color)
            
            # Bilgi etiketleri
            token_label = ttk.Label(info_frame, text="Token: -", style="Custom.TLabel")
            token_label.grid(row=0, column=0, padx=5, pady=2, sticky="w")
            
            buy_price_label = ttk.Label(info_frame, text="Alım Fiyatı: $-", style="Custom.TLabel")
            buy_price_label.grid(row=0, column=1, padx=5, pady=2, sticky="w")
            
            current_price_label = ttk.Label(info_frame, text="Güncel Fiyat: $-", style="Custom.TLabel")
            current_price_label.grid(row=0, column=2, padx=5, pady=2, sticky="w")
            
            profit_loss_label = ttk.Label(info_frame, text="Kâr/Zarar: $- (0%)", style="Custom.TLabel")
            profit_loss_label.grid(row=1, column=0, padx=5, pady=2, sticky="w")
            
            amount_label = ttk.Label(info_frame, text="Başlangıç Miktarı: 0 SOL", style="Custom.TLabel")
            amount_label.grid(row=1, column=1, padx=5, pady=2, sticky="w")
            
            token_amount_label = ttk.Label(info_frame, text="Token Miktarı: 0", style="Custom.TLabel")
            token_amount_label.grid(row=1, column=2, padx=5, pady=2, sticky="w")
            
            start_time_label = ttk.Label(info_frame, text="Başlangıç: -", style="Custom.TLabel")
            start_time_label.grid(row=2, column=0, padx=5, pady=2, sticky="w")
            
            duration_label = ttk.Label(info_frame, text="Süre: 0s", style="Custom.TLabel")
            duration_label.grid(row=2, column=1, padx=5, pady=2, sticky="w")
            
            progress = ttk.Progressbar(info_frame, length=100, mode='determinate', style="Custom.TProgressbar")
            progress.grid(row=2, column=2, padx=5, pady=2, sticky="w")
            
            progress_percent = ttk.Label(info_frame, text="0%", style="Custom.TLabel")
            progress_percent.grid(row=2, column=3, padx=2, pady=2, sticky="w")
            
            category_label = ttk.Label(info_frame, text="Kategori: -", style="Custom.TLabel")
            category_label.grid(row=3, column=0, padx=5, pady=2, sticky="w")
            
            liquidity_label = ttk.Label(info_frame, text="Likidite: $-", style="Custom.TLabel")
            liquidity_label.grid(row=3, column=1, padx=5, pady=2, sticky="w")
            
            market_cap_label = ttk.Label(info_frame, text="Market Cap: $-", style="Custom.TLabel")
            market_cap_label.grid(row=3, column=2, padx=5, pady=2, sticky="w")
            
            volume_label = ttk.Label(info_frame, text="Hacim (24s): $-", style="Custom.TLabel")
            volume_label.grid(row=4, column=0, padx=5, pady=2, sticky="w")
            
            highest_price_label = ttk.Label(info_frame, text="En Yüksek: $-", style="Custom.TLabel")
            highest_price_label.grid(row=4, column=1, padx=5, pady=2, sticky="w")
            
            remaining_amount_label = ttk.Label(info_frame, text="Kalan Miktar: 0 SOL", style="Custom.TLabel")
            remaining_amount_label.grid(row=4, column=2, padx=5, pady=2, sticky="w")
            
            tp_sl_label = ttk.Label(info_frame, text="TP/SL: -", style="Custom.TLabel")
            tp_sl_label.grid(row=5, column=0, columnspan=3, padx=5, pady=2, sticky="w")
            
            # Güncelleme fonksiyonunu başlat
            update_info_labels(
                trade_bot, mint_address, trade_window, token_label, buy_price_label, current_price_label,
                profit_loss_label, amount_label, token_amount_label, start_time_label,
                duration_label, progress, category_label, liquidity_label, market_cap_label,
                volume_label, highest_price_label, remaining_amount_label, tp_sl_label,
                progress_percent, text_color, profit_color, loss_color
            )
            
            # Log fonksiyonu
            def log_to_window(message):
                if trade_window.winfo_exists():
                    log_area.config(state='normal')
                    log_area.insert(tk.END, message + "\n")
                    log_area.see(tk.END)
                    log_area.config(state='disabled')
            
            trade_bot.trade_windows[mint_address] = log_to_window
            return trade_window, log_to_window
        
        except Exception as e:
            log_to_file(f"Pencere açma hatası: {e}")
            logger.error(f"Pencere açma hatası: {e}")
            return None, None
    
    # GUI thread'de çalıştır
    if trade_bot.root and trade_bot.root.winfo_exists():
        result = [None, None]
        
        def run_on_gui_thread():
            result[0], result[1] = create_window()
        
        trade_bot.root.after(0, run_on_gui_thread)
        
        # Sonucu bekle (kısa bir süre)
        if trade_bot._gui_queue:
            trade_bot._gui_queue.put(run_on_gui_thread)
        
        # Eğer bir log fonksiyonu zaten varsa, onu döndür
        if mint_address in trade_bot.trade_windows:
            return None, trade_bot.trade_windows[mint_address]
        
        # Yoksa, oluşturduğumuz log fonksiyonunu döndür
        return result[0], result[1]
    else:
        return None, None

def close_trade_window(trade_bot, mint_address):
    """
    Thread-safe işlem penceresini kapatır
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address: Token mint adresi
    """
    def close_window():
        try:
            if mint_address in open_windows and open_windows[mint_address].winfo_exists():
                open_windows[mint_address].destroy()
            if mint_address in open_windows:
                del open_windows[mint_address]
            if mint_address in trade_bot.trade_windows:
                del trade_bot.trade_windows[mint_address]
            
            logger.info(f"Pencere kapatıldı: {mint_address}")
        except Exception as e:
            logger.error(f"Pencere kapatma hatası: {e}")
    
    # GUI thread'de çalıştır
    if trade_bot.root and trade_bot.root.winfo_exists():
        trade_bot.root.after(0, close_window)
        
        # Kuyruk kullanımı
        if trade_bot._gui_queue:
            trade_bot._gui_queue.put(close_window)

def update_trade_window(trade_bot, mint_address, message):
    """
    İşlem penceresini günceller
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address: Token mint adresi
        message: Güncellenecek mesaj
    """
    if mint_address in trade_bot.trade_windows:
        log_function = trade_bot.trade_windows[mint_address]
        
        # GUI thread'de çalıştır
        if trade_bot.root and trade_bot.root.winfo_exists():
            trade_bot.root.after(0, lambda: log_function(message))
            
            # Kuyruk kullanımı
            if trade_bot._gui_queue:
                trade_bot._gui_queue.put(lambda: log_function(message))

def update_info_labels(trade_bot, mint_address, trade_window, token_label, buy_price_label, current_price_label, 
                       profit_loss_label, amount_label, token_amount_label, start_time_label, duration_label, 
                       progress, category_label, liquidity_label, market_cap_label, volume_label, 
                       highest_price_label, remaining_amount_label, tp_sl_label, progress_percent, 
                       text_color, profit_color, loss_color):
    """
    İşlem penceresi bilgilerini güncelleyen fonksiyon
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address: Token mint adresi
        trade_window: İşlem penceresi
        token_label: Token etiketi
        buy_price_label: Alım fiyatı etiketi
        current_price_label: Güncel fiyat etiketi
        profit_loss_label: Kâr/zarar etiketi
        amount_label: Miktar etiketi
        token_amount_label: Token miktarı etiketi
        start_time_label: Başlangıç zamanı etiketi
        duration_label: Süre etiketi
        progress: İlerleme çubuğu
        category_label: Kategori etiketi
        liquidity_label: Likidite etiketi
        market_cap_label: Market Cap etiketi
        volume_label: Hacim etiketi
        highest_price_label: En yüksek fiyat etiketi
        remaining_amount_label: Kalan miktar etiketi
        tp_sl_label: TP/SL etiketi
        progress_percent: İlerleme yüzdesi etiketi
        text_color: Metin rengi
        profit_color: Kâr rengi
        loss_color: Zarar rengi
    """
    if not trade_window.winfo_exists():
        return
    
    try:
        # Mevcut bilgileri al
        data = trade_bot.positions.get(mint_address, {})
        if not data:
            # Pozisyon kapanmış veya henüz açılmamış olabilir
            # Daha seyrek kontrol et
            trade_window.after(5000, lambda: update_info_labels(
                trade_bot, mint_address, trade_window, token_label, buy_price_label, current_price_label,
                profit_loss_label, amount_label, token_amount_label, start_time_label,
                duration_label, progress, category_label, liquidity_label, market_cap_label,
                volume_label, highest_price_label, remaining_amount_label, tp_sl_label,
                progress_percent, text_color, profit_color, loss_color
            ))
            return
            
        # Token bilgilerini güncelle (her zaman çalışır, hataya dayanıklı)
        try:
            token_info = trade_bot.price_cache.get(mint_address, {})
            token_name = token_info.get("symbol", "Bilinmeyen")
            # Token adını güncelle
            token_label.config(text=f"Token: {token_name}")
            
            # Eğer kategori bilgisi varsa, güncelle
            category = trade_bot.token_categories.get(mint_address, "bilinmeyen")
            category_label.config(text=f"Kategori: {category}")
            
            # Likidite ve market cap bilgilerini güncelle
            liquidity = token_info.get("liquidity_usd", 0)
            market_cap = token_info.get("market_cap", 0)
            liquidity_label.config(text=f"Likidite: ${format_price(liquidity)}")
            market_cap_label.config(text=f"Market Cap: ${format_price(market_cap)}")
            
            # Hacim bilgisini güncelle
            volume = token_info.get("volume", 0)
            volume_label.config(text=f"Hacim (24s): ${format_price(volume)}")
        except Exception as e:
            logger.warning(f"Token bilgisi güncelleme hatası: {e}")
            # Hata durumunda işlemi devam ettir
        
        # Fiyat bilgilerini güncelle - farklı kaynaklardan güvenilir veri almaya çalış
        try:
            buy_price = data.get("buy_price", 0)
            
            # Mevcut fiyatı belirlemek için birkaç farklı kaynağı dene:
            # 1. WebSocket fiyatı
            # 2. Cache'den fiyat
            # 3. Positions data
            current_price = trade_bot.websocket_prices.get(mint_address, 0)
            
            if current_price <= 0:
                current_price = trade_bot.price_cache.get(mint_address, {}).get("price_usd", 0)
            
            if current_price <= 0:
                current_price = data.get("buy_price", 0)  # En azından alım fiyatını göster
                
            # En yüksek fiyatı güncelle
            highest_price = data.get("highest_price", buy_price)
            
            # Fiyat etiketlerini düzgün formatlayarak güncelle
            buy_price_label.config(text=f"Alım Fiyatı: ${format_price(buy_price)}")
            current_price_label.config(text=f"Güncel Fiyat: ${format_price(current_price)}")
            highest_price_label.config(text=f"En Yüksek: ${format_price(highest_price)}")
            
            # Kâr/zarar hesaplama ve güncelleme
            profit_loss = (current_price - buy_price) * data.get("remaining_token_amount", 0)
            profit_loss_pct = ((current_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0
            profit_loss_label.config(
                text=f"Kâr/Zarar: ${format_price(profit_loss)} ({profit_loss_pct:.2f}%)",
                fg=profit_color if profit_loss >= 0 else loss_color
            )
            
            # Miktar bilgileri
            amount_label.config(text=f"Başlangıç Miktarı: {data.get('amount', 0):.4f} SOL")
            remaining_amount_label.config(text=f"Kalan Miktar: {data.get('remaining_amount', 0):.4f} SOL")
            token_amount_label.config(text=f"Token Miktarı: {data.get('remaining_token_amount', 0):.4f}")
            
            # Süre bilgileri
            start_time = trade_bot.trade_start_times.get(mint_address)
            if start_time:
                duration = datetime.now() - start_time
                duration_seconds = duration.total_seconds()
                start_time_label.config(text=f"Başlangıç: {start_time.strftime('%H:%M:%S')}")
                duration_label.config(text=f"Süre: {int(duration_seconds)}s")
                
                # İlerleme çubuğu
                max_duration = 300  # 5 dakika
                progress_value = min(duration_seconds / max_duration * 100, 100)
                progress['value'] = progress_value
                progress_percent.config(text=f"{progress_value:.1f}%")
            
            # TP/SL seviyeleri
            tp_sl_text = "TP/SL: "
            if data.get("tp_levels"):
                tp_sl_text += f"TP: {min([tp['profit'] for tp in data['tp_levels']])}% "
            if data.get("sl_levels"):
                tp_sl_text += f"SL: {max([sl['loss'] for sl in data['sl_levels']])}%"
            tp_sl_label.config(text=tp_sl_text)
            
        except Exception as e:
            logger.warning(f"Fiyat bilgisi güncelleme hatası: {e}")
            # Hata durumunda temel bilgileri koru
        
        # Bir sonraki güncellemeyi planla (500ms)
        trade_window.after(500, lambda: update_info_labels(
            trade_bot, mint_address, trade_window, token_label, buy_price_label, current_price_label,
            profit_loss_label, amount_label, token_amount_label, start_time_label,
            duration_label, progress, category_label, liquidity_label, market_cap_label,
            volume_label, highest_price_label, remaining_amount_label, tp_sl_label,
            progress_percent, text_color, profit_color, loss_color
        ))
        
    except Exception as e:
        logger.error(f"Bilgi etiketleri güncelleme hatası: {e}")
        # Pencereyi kapatmadan devam etmeyi dene
        if trade_window.winfo_exists():
            trade_window.after(5000, lambda: update_info_labels(
                trade_bot, mint_address, trade_window, token_label, buy_price_label, current_price_label,
                profit_loss_label, amount_label, token_amount_label, start_time_label,
                duration_label, progress, category_label, liquidity_label, market_cap_label,
                volume_label, highest_price_label, remaining_amount_label, tp_sl_label,
                progress_percent, text_color, profit_color, loss_color
            ))

def force_open_window(trade_bot, mint_address, trade_type, initial_content):
    """
    GUI thread'da pencere açmayı zorlar
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address: Token mint adresi
        trade_type: İşlem tipi
        initial_content: Başlangıç içeriği
        
    Returns:
        tuple: (pencere, log fonksiyonu)
    """
    if not trade_bot.root or not trade_bot.root.winfo_exists():
        logger.warning("GUI penceresi yok, pencere açılamadı")
        return None, None
    
    try:
        trade_window = tk.Toplevel(trade_bot.root)
        trade_window.title(f"{trade_type} - {mint_address}")
        trade_window.geometry("600x400")
        trade_window.protocol("WM_DELETE_WINDOW", lambda: close_trade_window(trade_bot, mint_address))
        
        # Log alanı
        log_area = scrolledtext.ScrolledText(trade_window, height=10, width=70, wrap=tk.WORD)
        log_area.pack(pady=5, padx=5, fill=tk.BOTH, expand=True)
        log_area.insert(tk.END, initial_content + "\n")
        log_area.config(state='disabled')
        
        # Bilgi frame'i
        info_frame = ttk.Frame(trade_window)
        info_frame.pack(pady=5, padx=5, fill=tk.X)
        
        # Renk ayarları
        text_color = "#000000" if not trade_settings["night_mode_enabled"] else "#FFFFFF"
        profit_color = "#008000"  # Yeşil
        loss_color = "#FF0000"    # Kırmızı
        bg_color = "#FFFFFF" if not trade_settings["night_mode_enabled"] else "#2B2B2B"
        
        trade_window.configure(bg=bg_color)
        info_frame.configure(style="Custom.TFrame")
        
        # Stil ayarları
        style = ttk.Style()
        style.configure("Custom.TFrame", background=bg_color)
        style.configure("Custom.TLabel", background=bg_color, foreground=text_color)
        style.configure("Custom.TProgressbar", background=profit_color, troughcolor=bg_color)
        
        # Bilgi etiketleri
        token_label = ttk.Label(info_frame, text="Token: -", style="Custom.TLabel")
        token_label.grid(row=0, column=0, padx=5, pady=2, sticky="w")
        
        buy_price_label = ttk.Label(info_frame, text="Alım Fiyatı: $-", style="Custom.TLabel")
        buy_price_label.grid(row=0, column=1, padx=5, pady=2, sticky="w")
        
        current_price_label = ttk.Label(info_frame, text="Güncel Fiyat: $-", style="Custom.TLabel")
        current_price_label.grid(row=0, column=2, padx=5, pady=2, sticky="w")
        
        profit_loss_label = ttk.Label(info_frame, text="Kâr/Zarar: $- (0%)", style="Custom.TLabel")
        profit_loss_label.grid(row=1, column=0, padx=5, pady=2, sticky="w")
        
        amount_label = ttk.Label(info_frame, text="Başlangıç Miktarı: 0 SOL", style="Custom.TLabel")
        amount_label.grid(row=1, column=1, padx=5, pady=2, sticky="w")
        
        token_amount_label = ttk.Label(info_frame, text="Token Miktarı: 0", style="Custom.TLabel")
        token_amount_label.grid(row=1, column=2, padx=5, pady=2, sticky="w")
        
        start_time_label = ttk.Label(info_frame, text="Başlangıç: -", style="Custom.TLabel")
        start_time_label.grid(row=2, column=0, padx=5, pady=2, sticky="w")
        
        duration_label = ttk.Label(info_frame, text="Süre: 0s", style="Custom.TLabel")
        duration_label.grid(row=2, column=1, padx=5, pady=2, sticky="w")
        
        progress = ttk.Progressbar(info_frame, length=100, mode='determinate', style="Custom.TProgressbar")
        progress.grid(row=2, column=2, padx=5, pady=2, sticky="w")
        
        progress_percent = ttk.Label(info_frame, text="0%", style="Custom.TLabel")
        progress_percent.grid(row=2, column=3, padx=2, pady=2, sticky="w")
        
        category_label = ttk.Label(info_frame, text="Kategori: -", style="Custom.TLabel")
        category_label.grid(row=3, column=0, padx=5, pady=2, sticky="w")
        
        liquidity_label = ttk.Label(info_frame, text="Likidite: $-", style="Custom.TLabel")
        liquidity_label.grid(row=3, column=1, padx=5, pady=2, sticky="w")
        
        market_cap_label = ttk.Label(info_frame, text="Market Cap: $-", style="Custom.TLabel")
        market_cap_label.grid(row=3, column=2, padx=5, pady=2, sticky="w")
        
        volume_label = ttk.Label(info_frame, text="Hacim (24s): $-", style="Custom.TLabel")
        volume_label.grid(row=4, column=0, padx=5, pady=2, sticky="w")
        
        highest_price_label = ttk.Label(info_frame, text="En Yüksek: $-", style="Custom.TLabel")
        highest_price_label.grid(row=4, column=1, padx=5, pady=2, sticky="w")
        
        remaining_amount_label = ttk.Label(info_frame, text="Kalan Miktar: 0 SOL", style="Custom.TLabel")
        remaining_amount_label.grid(row=4, column=2, padx=5, pady=2, sticky="w")
        
        tp_sl_label = ttk.Label(info_frame, text="TP/SL: -", style="Custom.TLabel")
        tp_sl_label.grid(row=5, column=0, columnspan=3, padx=5, pady=2, sticky="w")
        
        # Güncelleme fonksiyonunu başlat
        update_info_labels(
            trade_bot, mint_address, trade_window, token_label, buy_price_label, current_price_label,
            profit_loss_label, amount_label, token_amount_label, start_time_label,
            duration_label, progress, category_label, liquidity_label, market_cap_label,
            volume_label, highest_price_label, remaining_amount_label, tp_sl_label,
            progress_percent, text_color, profit_color, loss_color
        )
        
        # Log fonksiyonu
        def log_to_window(message):
            if trade_window.winfo_exists():
                log_area.config(state='normal')
                log_area.insert(tk.END, message + "\n")
                log_area.see(tk.END)
                log_area.config(state='disabled')
        
        trade_bot.trade_windows[mint_address] = log_to_window
        return trade_window, log_to_window
    
    except Exception as e:
        logger.error(f"Zorla pencere açma hatası: {e}")
        return None, None
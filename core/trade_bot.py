# -*- coding: utf-8 -*-
"""
Ana TradeBot sınıfı - tüm modülleri birleştirir
"""

from collections import defaultdict
from datetime import datetime
import asyncio
import threading
import queue
import time  # Added for sync_consumer
import tkinter as tk
from loguru import logger

from config import (
    trade_settings, DEBUG_MODE
)
from utils.logging_utils import log_to_file
from utils.formatting import format_price
from wallet.wallet_manager import wallet_manager
from analysis.token_analyzer import EnhancedTokenAnalyzer

# Modüller
from core.websocket_manager import (
    start_enhanced_websocket, add_token_subscription
)
from core.trade_window import (
    open_trade_window, close_trade_window, update_trade_window
)
from core.trade_monitor import monitor_positions
from core.rapid_cycle import start_rapid_cycle
from core.price_manager import (
    get_token_price, get_token_info, force_price_update
)
from core.buy_logic import process_buy_transaction
from core.sell_logic import (
    close_position_manually, emergency_sell, process_sell_transaction
)
from core.position_manager import (
    calculate_profit_percentage, take_partial_profit, update_position
)
from core.trade_analyzer import analyze_token_dynamics
from core.monitor_messages import (
    monitor_filtered_messages, auto_clear_console
)
from core.trade_strategies import apply_strategy_profile


class ThreadSafePriceQueue:
    """Thread-safe fiyat kuyruğu sınıfı."""
    def __init__(self, loop):
        self._async_queue = asyncio.Queue()
        self._sync_queue = queue.Queue()
        self._loop = loop
        
    async def put(self, item):
        """Asenkron metodla thread-safe ekleme"""
        await self._async_queue.put(item)
        self._sync_queue.put(item)
    
    def put_async(self, item):
        """Asenkron kuyruğa thread-safe ekleme"""
        asyncio.run_coroutine_threadsafe(
            self._async_queue.put(item), 
            self._loop
        )
        self._sync_queue.put(item)
    
    async def get_async(self):
        """Asenkron kuyruktan alma"""
        return await self._async_queue.get()
    
    def get_sync(self, block=True, timeout=None):
        """Senkron kuyruktan alma"""
        try:
            return self._sync_queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None


class ThreadSafeGUIQueue:
    """Thread-safe GUI kuyruğu sınıfı."""
    def __init__(self, root):
        self._queue = queue.Queue()
        self._root = root
        self._stop_event = threading.Event()
        self._mainloop_running = False
        
        def check_queue():
            try:
                while not self._queue.empty():
                    func, args = self._queue.get_nowait()
                    try:
                        func(*args)
                    except Exception as e:
                        logger.warning(f"GUI function error: {e}")
                    finally:
                        self._queue.task_done()
            except Exception as e:
                logger.warning(f"Queue check error: {e}")
            
            # Her 100 ms'de yeniden kontrol et
            if not self._stop_event.is_set() and self._root and self._root.winfo_exists():
                self._root.after(100, check_queue)
        
        # İlk kontrol işlemini başlat
        if self._root:
            self._root.after(100, check_queue)

    def put(self, func, *args):
        """Fonksiyonu ve argümanlarını kuyruğa ekle"""
        try:
            self._queue.put((func, args))
        except Exception as e:
            logger.warning(f"Queue put error: {e}")
    
    def set_mainloop_status(self, is_running):
        """Mainloop durumunu ayarlar"""
        self._mainloop_running = is_running

    def stop(self):
        """Kuyruk işlemcisini durdur"""
        self._stop_event.set()


class TradeBot:
    """TradeBot ana sınıfı."""
    def __init__(self, root):
        """
        TradeBot sınıfını başlatır.
        
        Args:
            root: Tkinter root penceresi
        """
        # Temel özellikler
        self.root = root  # tkinter ana penceresi
        self.wallet = wallet_manager
        self.client = wallet_manager.client
        self.config = trade_settings  # Referans kolaylığı için
        
        # Pozisyon ve token verileri
        self.positions = {}
        self.processed_mints = set()
        self.highest_price = {}
        self.past_trades = []
        self.price_history = defaultdict(list)
        self.price_cache = {}
        self.last_price_update = {}
        self.websocket_prices = {}
        self.first_seen_mints = {}
        self.daily_trades = []
        self.initial_prices = {}
        self.trade_start_times = {}
        self.token_categories = {}
        self.positions_by_category = defaultdict(int)
        self.pump_start_times = {}
        self.pending_buys = set()
        
        # WebSocket ve döngüler
        self.websocket_active = False
        self.subscribed_tokens = {"So11111111111111111111111111111111111111112"}  # SOL token
        self.rapid_cycle_active = False
        self.last_rapid_cycle = {}
        self.websocket = None
        
        # UI
        self.trade_windows = {}
        self._last_displayed_price = {}  # Son gösterilen fiyatları tutmak için
        
        # Analiz
        self.analyzer = EnhancedTokenAnalyzer()
        
        # State kaydetme/yükleme
        self.save_state = None
        self.load_state = None
        
        # Event loop ve kuyruklar
        self._loop = asyncio.get_event_loop()
        self.price_queue = ThreadSafePriceQueue(self._loop)
        self._gui_queue = ThreadSafeGUIQueue(root)
        
        # Kuyruk tüketicilerini başlat
        self.start_async_price_queue_consumer()
        self.start_sync_price_queue_consumer()
        
        # Ana thread'de periyodik işlemleri başlat
        self.process_price_updates()
        
        # Son fiyat istekleri için sözlük
        self._last_price_requests = {}

    def start_async_price_queue_consumer(self):
        """Asenkron kuyruk tüketicisini başlatır."""
        async def async_consumer():
            while True:
                try:
                    # Asenkron kuyruktan al
                    item = await self.price_queue.get_async()
                    if item:
                        mint_address, price = item
                        # Token dinamiklerini analiz et
                        await self.process_price_update_async(mint_address, price)
                except Exception as e:
                    logger.error(f"Async kuyruk hatası: {e}")
                await asyncio.sleep(0.1)

        def run_async_consumer():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(async_consumer())
            except Exception as e:
                logger.error(f"Async tüketici hatası: {e}")

        threading.Thread(
            target=run_async_consumer, 
            daemon=True
        ).start()

    def start_sync_price_queue_consumer(self):
        """Senkron kuyruk tüketicisini başlatır."""
        def sync_consumer():
            while True:
                try:
                    # Senkron kuyruğu kontrol et
                    item = self.price_queue.get_sync(block=False)
                    if item:
                        mint_address, price = item
                        self.process_price_update_sync(mint_address, price)
                except queue.Empty:
                    pass
                except Exception as e:
                    logger.error(f"Sync kuyruk hatası: {e}")
                time.sleep(0.1)

        def start_sync_thread():
            consumer_thread = threading.Thread(target=sync_consumer, daemon=True)
            consumer_thread.start()

        self._gui_queue.put(start_sync_thread)

    def process_price_updates(self):
        """Düzenli fiyat güncellemelerini yönetir."""
        def periodic_price_update():
            try:
                # Abonelik yapılmış tokenlerin fiyatlarını düzenli olarak güncelle
                for mint_address in list(self.subscribed_tokens):
                    try:
                        force_price_update(self, mint_address)
                    except Exception as e:
                        logger.error(f"Fiyat güncelleme hatası: {mint_address} - {e}")
                
                # Tekrar zamanlayın
                if self.root and self.root.winfo_exists():
                    self.root.after(15000, periodic_price_update)  # 15 saniyede bir güncelle
            except Exception as e:
                logger.error(f"Periyodik fiyat güncelleme hatası: {e}")
                # Hata durumunda bile tekrar zamanlayın
                if self.root and self.root.winfo_exists():
                    self.root.after(15000, periodic_price_update)
        
        # İlk çağrıyı başlat
        if self.root:
            self.root.after(15000, periodic_price_update)

    async def process_price_update_async(self, mint_address, price):
        """
        Asenkron fiyat işleme
        
        Args:
            mint_address: Token mint adresi
            price: Token fiyatı
        """
        try:
            # Token bilgilerini al
            token_info = await get_token_info(self, mint_address)
            
            # Token dinamiklerini analiz et
            await analyze_token_dynamics(
                self, 
                mint_address, 
                price, 
                token_info, 
                0  # Örnek price_change_pct
            )
        except Exception as e:
            logger.error(f"Asenkron fiyat işleme hatası: {e}")

    def process_price_update_sync(self, mint_address, price):
        """
        Senkron (GUI) fiyat işleme - thread-safe
        
        Args:
            mint_address: Token mint adresi
            price: Token fiyatı
        """
        def update_gui():
            try:
                self.websocket_prices[mint_address] = price
                self.update_log(
                    mint_address, 
                    f"Fiyat Güncellendi: {mint_address} - ${price:.8f}"
                )
                
                if mint_address in self.trade_windows:
                    self.trade_windows[mint_address](f"Fiyat: ${price:.8f}")
            except Exception as e:
                logger.error(f"Senkron fiyat işleme hatası: {e}")

        self._gui_queue.put(update_gui)

    def update_log(self, mint_address, message):
        """
        Log mesajlarını hem dosyaya hem de ilgili pencereye günceller
        
        Args:
            mint_address: Token mint adresi
            message: Log mesajı
        """
        try:
            current_time = datetime.now().strftime("%H:%M:%S")
            log_message = f"[{current_time}] {message}"
            log_to_file(log_message)
            
            if mint_address and mint_address in self.trade_windows:
                self.trade_windows[mint_address](message)
            else:
                print(log_message)  # Konsola da yaz
        except Exception as e:
            log_to_file(f"Log güncelleme hatası: {e}")

    def check_token_exists_in_any_positions(self, mint_address):
        """
        Token'ın herhangi bir pozisyonda olup olmadığını kontrol eder
        
        Args:
            mint_address (str): Token mint adresi
            
        Returns:
            bool: Token bir pozisyonda ise True, değilse False
        """
        # 1. Aktif pozisyonlarda kontrol
        if mint_address in self.positions:
            return True
            
        # 2. Geçmiş işlemlerde kontrol
        for trade in self.past_trades:
            if trade.get("mint") == mint_address:
                return True
        
        # 3. Eğer token adresini değiştiren bir format varsa (pump sonekleri gibi)
        base_address = mint_address
        if base_address.endswith("pump"):
            base_address = base_address[:-4]  # "pump" sonekini kaldır
            
        for pos_mint in self.positions:
            if pos_mint.startswith(base_address):
                return True
        
        # Hiçbir pozisyonda bulunamadı
        return False

    async def monitor_positions(self):
        """
        Açık pozisyonları sürekli olarak izler ve TP/SL kontrollerini yapar.
        """
        from core.trade_analyzer import analyze_token_dynamics
        
        while True:
            try:
                for mint_address in list(self.positions.keys()):
                    try:
                        # Token bilgilerini al
                        token_info = await get_token_info(self, mint_address, force_update=True)
                        
                        if token_info:
                            current_price = token_info.get("price_usd", 0)
                            
                            # Token dinamiklerini analiz et
                            await analyze_token_dynamics(
                                self, 
                                mint_address, 
                                current_price, 
                                token_info, 
                                0  # Örnek price_change_pct
                            )
                    except Exception as e:
                        self.update_log(mint_address, f"Pozisyon izleme hatası: {e}")
                
                # Belirli bir aralıkta çalış
                await asyncio.sleep(5)  # 5 saniyede bir kontrol et
            
            except Exception as e:
                log_to_file(f"Genel pozisyon izleme hatası: {e}")
                await asyncio.sleep(5)

    def start_rapid_cycle(self):
        from gotnw_tradebot.core.rapid_cycle import start_rapid_cycle
        return start_rapid_cycle(self)

    # Ana işlevleri, artık modülleri kullanıyor
    async def buy(self, mint_address, amount=None, detection_time=None, manual=False,
                  pump_detected=False, momentum_detected=False, dip_detected=False, ai_detected=False):
        """
        Token alımını başlatır (şimdi core modülünü kullanıyor)
        
        Args:
            mint_address (str): Token mint adresi
            amount (float, optional): Alım miktarı
            detection_time (datetime, optional): Tespit zamanı
            manual (bool): Manuel alım mı?
            pump_detected (bool): Pump tespit edildi mi?
            momentum_detected (bool): Momentum tespit edildi mi?
            dip_detected (bool): Dip tespit edildi mi?
            ai_detected (bool): AI tarafından tespit edildi mi?
            
        Returns:
            bool: İşlem başarısı
        """
        return await process_buy_transaction(
            self, mint_address, amount, detection_time, manual,
            pump_detected, momentum_detected, dip_detected, ai_detected
        )

    async def close_position_manually(self, mint_address):
        """
        Pozisyonu manuel olarak kapatır
        
        Args:
            mint_address (str): Token mint adresi
            
        Returns:
            bool: İşlem başarısı
        """
        return await close_position_manually(self, mint_address)

    # Başlatma fonksiyonları
    async def start_all_tasks(self):
        """
        Tüm asenkron görevleri başlatır
        """
        tasks = []
        
        # Pozisyon izleme
        tasks.append(asyncio.create_task(monitor_positions(self)))
        
        # Mesaj izleme
        tasks.append(asyncio.create_task(monitor_filtered_messages(self)))
        
        # Konsol temizleme
        tasks.append(asyncio.create_task(auto_clear_console(self)))
        
        # WebSocket başlatma
        tasks.append(asyncio.create_task(start_enhanced_websocket(self)))
        
        # SOL token'ını WebSocket'e ekle
        await add_token_subscription(self, "So11111111111111111111111111111111111111112")
        
        # Hızlı döngü etkinse başlat
        if trade_settings["rapid_cycle_enabled"]:
            tasks.append(asyncio.create_task(start_rapid_cycle(self)))
        
        return tasks

    # Yardımcı fonksiyonlar
    def format_price(self, price):
        """Fiyatı formatlar"""
        return format_price(price)

    async def display_menu(self):
        """Konsol menüsünü gösterir"""
        # Menü modülü içindeki display_menu fonksiyonunu çağırır
        from core.menu_handler import display_menu
        return await display_menu(self)

    async def start_bot(self, console_mode=True, gui_mode=False):
        """
        Bot uygulamasını başlatan ana fonksiyon
        """
        # Görevleri oluştur
        tasks = []
        
        # Temel görevler
        tasks.append(asyncio.create_task(self.monitor_positions()))  # Bu satırı kontrol edin
        tasks.append(asyncio.create_task(monitor_filtered_messages(self)))
        tasks.append(asyncio.create_task(auto_clear_console(self)))

        return tasks
# -*- coding: utf-8 -*-
import asyncio
import os
import json
import traceback
import base58
from datetime import datetime, timezone
import tkinter as tk
from tkinter import ttk, scrolledtext
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from loguru import logger

from gotnw_tradebot.config import (
    trade_settings, open_windows, STATE_FILE, LOG_PATH, 
    STRATEGY_PROFILES, current_strategy, INPUT_FILE, APP_ROOT
)
from gotnw_tradebot.utils import (
    animated_text, log_to_file, print_wallet_info, 
    check_night_mode_transition, get_sol_price
)
from gotnw_tradebot.wallet import wallet_manager, get_available_balance, async_input, WalletManager
from gotnw_tradebot.core import TradeBot
from gotnw_tradebot.analysis import EnhancedTokenAnalyzer, TokenAnalyzer
from gotnw_tradebot.gui import start_gui

# İşlenen mint adreslerini takip eden set
processed_mints = set()
last_processed_time = 0

async def save_state(trade_bot):
    """Mevcut bot durumunu kaydetme fonksiyonu"""
    try:
        wallet_data = []
        for wallet in trade_bot.wallet.wallets:
            keypair = wallet["keypair"]
            wallet_data.append({
                "pubkey": str(keypair.pubkey()),
                "private_key": base58.b58encode(keypair.secret()).decode('utf-8'),
                "connected": wallet["connected"]
            })
        
        state = {
            "positions": trade_bot.positions,
            "settings": trade_settings,
            "first_seen_mints": {mint: ts.strftime('%Y-%m-%d %H:%M:%S') for mint, ts in trade_bot.first_seen_mints.items()},
            "past_trades": trade_bot.past_trades,
            "current_strategy": current_strategy,
            "wallets": wallet_data,
            "active_wallet_index": trade_bot.wallet.active_wallet_index,
            "processed_mints": list(trade_bot.processed_mints)
        }
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, default=str)
        animated_text("💾 Durum başarıyla kaydedildi")
        logger.info(f"Kaydedilen cüzdan sayısı: {len(wallet_data)}")
        if wallet_data:
            logger.info(f"Örnek cüzdan: {wallet_data[0]['pubkey']}")
    except Exception as e:
        log_to_file(f"❌ Durum kaydedilemedi: {e}")
        logger.error(f"Durum kaydedilemedi: {e}")
        traceback.print_exc()

async def load_state(trade_bot):
    """Kaydedilmiş bot durumunu yükleme fonksiyonu"""
    try:
        global trade_settings, current_strategy
        
        if not os.path.exists(STATE_FILE):
            animated_text(f"⚠️ Kaydedilmiş durum bulunamadı, varsayılan ayarlar kullanılıyor")
            logger.warning("Durum dosyası bulunamadı")
            return
            
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            state = json.load(f)
        
        logger.info("Durum dosyası başarıyla okundu.")
            
        if "positions" in state:
            trade_bot.positions = state["positions"]
            
        if "settings" in state:
            trade_settings.update(state["settings"])
            
        if "first_seen_mints" in state:
            try:
                trade_bot.first_seen_mints = {mint: datetime.strptime(ts, '%Y-%m-%d %H:%M:%S') for mint, ts in state["first_seen_mints"].items()}
            except ValueError:
                trade_bot.first_seen_mints = {mint: datetime.fromisoformat(ts) for mint, ts in state["first_seen_mints"].items()}
                                      
        if "past_trades" in state:
            for trade in state["past_trades"]:
                if isinstance(trade["timestamp"], str):
                    try:
                        trade["timestamp"] = datetime.strptime(trade["timestamp"], '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        trade["timestamp"] = datetime.fromisoformat(trade["timestamp"])
            trade_bot.past_trades = state["past_trades"]
            
        if "current_strategy" in state:
            current_strategy = state["current_strategy"]
        
        if "processed_mints" in state:
            trade_bot.processed_mints = set(state["processed_mints"])
        
        if "wallets" in state and "active_wallet_index" in state:
            logger.info(f"Cüzdan verileri bulundu. Yüklenecek cüzdan sayısı: {len(state['wallets'])}")
            try:
                wallet_manager.wallets = []
                wallet_manager.active_wallet_index = -1
                
                for wallet_data in state["wallets"]:
                    try:
                        seed_bytes = base58.b58decode(wallet_data["private_key"])
                        keypair = Keypair.from_seed(seed_bytes[:32])
                        wallet_manager.wallets.append({
                            "keypair": keypair,
                            "connected": wallet_data.get("connected", True)
                        })
                        logger.info(f"Cüzdan yüklendi: {keypair.pubkey()}")
                    except Exception as e:
                        log_to_file(f"Cüzdan yükleme hatası: {e}")
                        logger.error(f"Cüzdan yükleme hatası: {e}")
                        traceback.print_exc()
                
                if wallet_manager.wallets:
                    active_index = state["active_wallet_index"]
                    if 0 <= active_index < len(wallet_manager.wallets):
                        wallet_manager.active_wallet_index = active_index
                        logger.info(f"Aktif cüzdan ayarlandı: {wallet_manager.wallets[active_index]['keypair'].pubkey()}")
                        animated_text(f"Aktif cüzdan: {wallet_manager.wallets[active_index]['keypair'].pubkey()}")
                    else:
                        logger.warning(f"Geçersiz aktif cüzdan indeksi: {active_index}")
                else:
                    logger.warning("Cüzdanlar yüklendi ancak liste boş.")
            except Exception as e:
                log_to_file(f"Cüzdan yükleme ana hatası: {e}")
                logger.error(f"Cüzdan yükleme ana hatası: {e}")
                traceback.print_exc()
        else:
            logger.warning("Durum dosyasında cüzdan verileri bulunamadı.")
            
        animated_text("📂 Durum başarıyla yüklendi")
    except Exception as e:
        log_to_file(f"❌ Durum yüklenemedi: {e}")
        logger.error(f"Durum yüklenemedi: {e}")
        traceback.print_exc()

async def run_tk(root):
    """tkinter ve asyncio'yu entegre eden yardımcı fonksiyon"""
    while True:
        try:
            root.update()
            await asyncio.sleep(0.01)
        except tk.TclError:
            break

async def start_bot(console_mode=True, gui_mode=False):
    """Bot uygulamasını başlatan ana fonksiyon"""
    # Loguru yapılandırması
    logger.remove()  # Varsayılan sink'i kaldır
    logger.add(os.path.join(LOG_PATH, "tradebot.log"), 
              rotation="1 MB", 
              level="DEBUG", 
              format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")
    logger.add(lambda msg: print(msg), level="INFO", format="{message}")
    
    # Klasörleri oluştur
    if not os.path.exists(LOG_PATH):
        os.makedirs(LOG_PATH)
        logger.info(f"Log dizini oluşturuldu: {LOG_PATH}")

    animated_text("🚀 GOTNW TradeBot Başlatılıyor...")
    animated_text("ℹ️ Veriler yükleniyor...")

    # Root oluştur
    root = tk.Tk()
    if not gui_mode:
        root.withdraw()  # Konsol arayüzü için başlangıçta gizle

    # TradeBot oluştur
    trade_bot = TradeBot(root)
    trade_bot.save_state = lambda: save_state(trade_bot)
    trade_bot.load_state = lambda: load_state(trade_bot)
    trade_bot.pending_buys = set()  # pending_buys'ı burada başlatıyoruz
    
    wallet_manager.trade_bot = trade_bot

    # Durum yüklemeyi dene
    try:
        await trade_bot.load_state()
    except Exception as e:
        logger.error(f"Durum yükleme hatası: {e}")
        animated_text("❌ Durum yüklenirken hata oluştu, varsayılan ayarlar kullanılacak")
        traceback.print_exc()

    # AI Modellerini Yükle
    try:
        from gotnw_tradebot.config import AI_MODEL_FILE
        trade_bot.analyzer.load_models(AI_MODEL_FILE.replace(".pkl", ""))
        animated_text("🧠 AI modelleri yüklendi")
        
        # AI modelleri yoksa veya düzgün yüklenmediyse
        if not hasattr(trade_bot.analyzer.isolation_forest, "_fitted") or not getattr(trade_bot.analyzer.isolation_forest, "_fitted", False):
            animated_text("🧠 AI modelleri henüz eğitilmemiş, otomatik eğitim başlatılıyor...")
            
            # Yeterli veri yoksa AI özelliklerini devre dışı bırak
            if len(trade_bot.analyzer.price_history) < 10:
                animated_text("⚠️ AI özellikleri için yeterli veri yok, özellikler geçici olarak devre dışı")
                trade_settings["ai_enabled"] = False
            else:
                # Modelleri eğitmeyi dene
                try:
                    pump_success = trade_bot.analyzer.train_pump_detection_model()
                    duration_success = trade_bot.analyzer.train_pump_duration_model()
                    price_success = trade_bot.analyzer.train_price_prediction_model()
                    
                    if pump_success or duration_success or price_success:
                        animated_text("✅ AI modelleri başarıyla eğitildi!")
                    else:
                        animated_text("⚠️ AI modelleri eğitilemedi, veriler zamanla toplanacak")
                        trade_settings["ai_enabled"] = False
                except Exception as e:
                    log_to_file(f"AI model eğitimi hatası: {e}")
                    logger.error(f"AI model eğitimi hatası: {e}")
                    animated_text("⚠️ AI model eğitimi başarısız, özellikler geçici olarak devre dışı")
                    trade_settings["ai_enabled"] = False
    except Exception as e:
        logger.error(f"AI modülleri yüklenemedi: {e}")
        animated_text("ℹ️ AI modelleri bulunamadı, yeni model eğitilebilir")

    # Görevleri oluştur
    tasks = []
    
    # GUI için görevler
    if gui_mode:
        start_gui(trade_bot)
    else:
        tasks.append(asyncio.create_task(run_tk(root)))
    
    # Temel görevler
    tasks.extend([
        asyncio.create_task(trade_bot.monitor_positions()),
        asyncio.create_task(monitor_filtered_messages(trade_bot)),
        asyncio.create_task(auto_clear_console(trade_bot))
    ])

    # İsteğe bağlı görevler
    if trade_settings["rapid_cycle_enabled"]:
        animated_text("⚡ Hızlı döngü başlatılıyor...")
        tasks.append(asyncio.create_task(trade_bot.start_rapid_cycle()))

    # WebSocket başlat
    tasks.append(asyncio.create_task(trade_bot.start_enhanced_websocket()))
    await trade_bot.add_websocket_token("So11111111111111111111111111111111111111112")
    
    check_night_mode_transition()

    # Başlatma tamamlandı
    animated_text("✅ TradeBot başlatıldı!")
    if console_mode:
        animated_text("\nℹ️ Komutlar:")
        animated_text("- token [mint_address]: Token'ı izlemeye başla")
        animated_text("- buy [mint_address] [amount_sol]: Token satın al")
        animated_text("- close [mint_address]: Pozisyonu kapat")
        animated_text("- menu: Menüyü göster")
        animated_text("- exit: Programı kapat")
        animated_text("- q: Açık pencereyi/pozisyonu kapat")
        animated_text("- 24: GUI arayüzünü başlat")
    
    # Ekran bilgilerini güncelle
    await update_display(trade_bot)
    
    # Konsol modu aktifse komut dinlemeye başla
    if console_mode:
        await console_command_loop(trade_bot, tasks, root)
    else:
        # Sadece görevleri bekleriz
        await asyncio.gather(*tasks)

async def console_command_loop(trade_bot, tasks, root):
    """Konsol komutlarını işleyen döngü"""
    while True:
        command = (await async_input("\n> ")).strip().lower()

        if command == "exit":
            animated_text("👋 Programdan çıkılıyor...")
            logger.info("Programdan çıkılıyor...")
            for task in tasks:
                task.cancel()
            if trade_bot.websocket_active:
                await trade_bot.stop_websocket()
            root.destroy()
            break

        elif command == "menu":
            await trade_bot.display_menu()
            await update_display(trade_bot)

        elif command.startswith("token "):
            mint_address = command.split("token ")[1].strip()
            await trade_bot.add_websocket_token(mint_address)
            await update_display(trade_bot)

        elif command.startswith("buy "):
            parts = command.split("buy ")[1].strip().split()
            if len(parts) >= 1:
                mint_address = parts[0]
                amount = float(parts[1]) if len(parts) > 1 else trade_settings["buy_amount_sol"]
                await trade_bot.buy(mint_address, amount, manual=True)
            else:
                animated_text("❌ Geçersiz komut! Örnek: buy [mint_address] [amount_sol]")
            await update_display(trade_bot)

        elif command.startswith("close "):
            mint_address = command.split("close ")[1].strip()
            if mint_address in trade_bot.positions:
                result = await trade_bot.close_position_manually(mint_address)
                if result:
                    animated_text(f"✅ Pozisyon kapatıldı: {mint_address}")
                else:
                    animated_text(f"❌ Pozisyon kapatılamadı: {mint_address}")
            else:
                animated_text(f"❌ Aktif pozisyon bulunamadı: {mint_address}")
            await update_display(trade_bot)

        elif command == "q":
            if open_windows:
                mint_address = next(iter(open_windows))
                result = await trade_bot.close_position_manually(mint_address)
                if result:
                    animated_text(f"✅ Pozisyon kapatıldı: {mint_address}")
                elif mint_address in open_windows:
                    open_windows.remove(mint_address)
                    animated_text(f"ℹ️ Pencere kapatıldı: {mint_address}")
            else:
                animated_text("ℹ️ Açık pencere veya pozisyon yok")
            await update_display(trade_bot)

        elif command in ["gui", "24"]:
            animated_text("GUI arayüzü başlatılıyor...")
            start_gui(trade_bot)
            await update_display(trade_bot)

        elif command == "new":
            animated_text("Yeni sade mod başlatılıyor...")
            logger.info("Yeni sade mod başlatılıyor")
            for task in tasks:
                task.cancel()
            if trade_bot.websocket_active:
                await trade_bot.stop_websocket()
            root.destroy()
            await new_main()
            break

        elif command.strip():
            animated_text(f"❌ Tanınmayan komut: {command}")

async def update_display(trade_bot):
    """Cüzdan bilgilerini ekranda gösterir"""
    try:
        sol_price = await get_sol_price() or 0
        balance = await wallet_manager.get_balance()
        current_wallet = "Bağlı değil" if wallet_manager.active_wallet_index == -1 else str(wallet_manager.wallets[wallet_manager.active_wallet_index]["keypair"].pubkey())
        print_wallet_info(current_wallet, balance, sol_price)
    except Exception as e:
        log_to_file(f"Ekran güncelleme hatası: {e}")
        logger.error(f"Ekran güncellenemedi: {e}")

async def monitor_filtered_messages(trade_bot):
    """INPUT_FILE dosyasını izler ve yeni tokenları işlemeye alır"""
    # Mevcut monitor_filtered_messages fonksiyonunun içeriğini buraya kopyalayın

async def auto_clear_console(trade_bot):
    """10 dakikada bir konsolu temizler ve sadece cüzdan bilgilerini gösterir"""
    # Mevcut auto_clear_console fonksiyonunun içeriğini buraya kopyalayın

async def new_main():
    """Yeni ana fonksiyon - loguru kullanır ve daha sade yapıdadır"""
    logger.add("tradebot.log", rotation="1 MB")
    logger.info("Bot başlatılıyor...")
    try:
        wallet_mgr = WalletManager()
        trade_bot = TradeBot(None)  # GUI olmadan başlatma
        token_analyzer = TokenAnalyzer()
        await asyncio.gather(
            token_analyzer.start_pool_detection(),
            trade_bot.start_auto_buy()
        )
    except Exception as e:
        logger.error(f"Bot başlatma hatası: {e}")

def start_application(console_mode=True, gui_mode=False):
    """Uygulamayı başlatan ana fonksiyon"""
    try:
        asyncio.run(start_bot(console_mode, gui_mode))
    except Exception as e:
        print(f"Uygulama başlatma hatası: {e}")
        import traceback
        traceback.print_exc()
        input("Devam etmek için bir tuşa basın...")

if __name__ == "__main__":
    start_application(console_mode=True)
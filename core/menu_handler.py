# -*- coding: utf-8 -*-
"""
Menü işlem modülü - konsol komutlarını işler
"""

import asyncio
from datetime import datetime
import os
from loguru import logger

from gotnw_tradebot.config import (
    trade_settings, last_action_message, current_strategy,
    STRATEGY_PROFILES, DAILY_REPORT_FILE
)
from gotnw_tradebot.utils.console_utils import animated_text, clear_screen
from gotnw_tradebot.utils.trade_utils import check_night_mode_transition
from gotnw_tradebot.wallet.wallet_manager import wallet_manager, async_input, get_available_balance
from gotnw_tradebot.utils.network_utils import get_sol_price


async def display_menu(trade_bot):
    """
    Kullanıcıya komut menüsünü gösterir ve seçimlerini işler
    
    Args:
        trade_bot: TradeBot nesnesi
        
    Returns:
        bool: Menüden çıkılacaksa True, devam edilecekse False
    """
    global last_action_message, current_strategy
    
    clear_screen()
    options = [
        "0. Menüden Çık 🚪",
        "1. Cüzdan Bağla 👛",
        "2. Cüzdan Değiştir 👛",
        "3. Otomatik Alımı Aç/Kapat 🛒",
        "4. Otomatik Satışı Aç/Kapat 🛒",
        "5. Alım Miktarını Ayarla 💰",
        "6. TP ve SL Ayarlarını Düzenle ⚙️",
        "7. Durumu Kaydet 💾",
        "8. Durumu Yükle 💾",
        "9. Manuel Alım 🖐️",
        "10. Manuel Satım 🖐️",
        "11. Günlük Rapor Oluştur 📊",
        "12. Simülasyon Modunu Aç/Kapat 🔄",
        "13. Strateji Profilini Değiştir ⚙️",
        "14. Gece Modunu Aç/Kapat 🌙",
        "15. Sniping Özelliğini Aç/Kapat 🎯",
        "16. Hızlı Döngüyü Aç/Kapat ⚡",
        "17. Momentum Tabanlı Alımı Aç/Kapat 📈",
        "18. Balina Takibini Aç/Kapat 🐋",
        "19. Volatilite Tabanlı İşlemi Aç/Kapat 📊",
        "20. Likidite Çıkış Stratejisini Aç/Kapat 💧",
        "21. AI Özelliklerini Aç/Kapat 🤖",
        "22. AI Modellerini Eğit/Yükle 🧠",
        "23. Token Analiz Raporu 📝",
        "24. GUI Arayüzünü Başlat 🖥️",
        "25. Debug Modunu Aç/Kapat 🐞"
    ]
    print("\n=== GOTNW TradeBot Menü ===")
    for option in options:
        print(option)
    print(f"\nSon işlem: {last_action_message}")
    choice = await async_input("Seçiminizi yapın (0-25): ")
    choice = choice.strip()

    if choice == "0":
        animated_text("ℹ️ Menüden çıkılıyor...")
        return True
    
    elif choice == "1":
        private_key = await async_input("Cüzdan özel anahtarını girin: ")
        last_action_message = await wallet_manager.connect_wallet(private_key.strip())
        await async_input("Devam etmek için Enter'a bas")
    
    elif choice == "2":
        if wallet_manager.wallets:
            print("\nMevcut Cüzdanlar:")
            for i, wallet in enumerate(wallet_manager.wallets, start=1):
                print(f"{i}. {wallet['keypair'].pubkey()}")
            try:
                index = int((await async_input("Cüzdan numarasını girin (1, 2, ...): ")).strip()) - 1
                last_action_message = await wallet_manager.switch_wallet(index)
            except ValueError:
                last_action_message = "❌ Geçersiz indeks, lütfen sayı girin"
                animated_text(last_action_message)
        else:
            last_action_message = "❌ Hiçbir cüzdan bağlı değil"
            animated_text(last_action_message)
        await async_input("Devam etmek için Enter'a bas")
    
    elif choice == "3":
        trade_settings["autobuy_enabled"] = not trade_settings["autobuy_enabled"]
        last_action_message = f"Otomatik alım {'açıldı' if trade_settings['autobuy_enabled'] else 'kapatıldı'}"
        animated_text(last_action_message)
        await async_input("Devam etmek için Enter'a bas")
    
    elif choice == "4":
        trade_settings["autosell_enabled"] = not trade_settings["autosell_enabled"]
        last_action_message = f"Otomatik satış {'açıldı' if trade_settings['autosell_enabled'] else 'kapatıldı'}"
        animated_text(last_action_message)
        await async_input("Devam etmek için Enter'a bas")
    
    elif choice == "5":
        try:
            amount = float((await async_input("Alım miktarı (SOL): ")).strip())
            trade_settings["buy_amount_sol"] = amount
            last_action_message = f"Alım miktarı {amount} SOL olarak ayarlandı"
            animated_text(last_action_message)
        except ValueError:
            last_action_message = "❌ Geçersiz miktar, lütfen sayı girin"
            animated_text(last_action_message)
        await async_input("Devam etmek için Enter'a bas")
    
    elif choice == "6":
        try:
            tp_levels = (await async_input("TP seviyelerini girin (örn: 20:25,50:25,100:25,150:100): ")).strip()
            sl_levels = (await async_input("SL seviyelerini girin (örn: -5:50,-10:100): ")).strip()
            trade_settings["sell_profit_targets"] = [
                {"profit": float(p.split(':')[0]), "sell_percentage": float(p.split(':')[1])}
                for p in tp_levels.split(',')
            ]
            trade_settings["sell_stop_loss_levels"] = [
                {"loss": float(p.split(':')[0]), "sell_percentage": float(p.split(':')[1])}
                for p in sl_levels.split(',')
            ]
            last_action_message = "TP ve SL seviyeleri güncellendi"
            animated_text(last_action_message)
        except ValueError:
            last_action_message = "❌ Geçersiz format, lütfen doğru formatta girin"
            animated_text(last_action_message)
        await async_input("Devam etmek için Enter'a bas")
    
    elif choice == "7":
        if trade_bot.save_state:
            await trade_bot.save_state()
            last_action_message = "Durum kaydedildi"
        else:
            last_action_message = "❌ Durum kaydetme fonksiyonu kullanılamıyor"
        await async_input("Devam etmek için Enter'a bas")
    
    elif choice == "8":
        if trade_bot.load_state:
            await trade_bot.load_state()
            last_action_message = "Durum yüklendi"
        else:
            last_action_message = "❌ Durum yükleme fonksiyonu kullanılamıyor"
        await async_input("Devam etmek için Enter'a bas")
    
    elif choice == "9":
        try:
            mint_address = (await async_input("Alım yapılacak tokenın mint adresini girin: ")).strip()
            amount = float(
                (await async_input(f"Alım miktarı (SOL, mevcut: {await get_available_balance()}): ")).strip()
            )
            await trade_bot.buy(mint_address, amount, manual=True)
            last_action_message = f"Manuel alım başlatıldı: {mint_address}, {amount} SOL"
        except ValueError:
            last_action_message = "❌ Geçersiz miktar, lütfen sayı girin"
            animated_text(last_action_message)
        await async_input("Devam etmek için Enter'a bas")
    
    elif choice == "10":
        try:
            mint_address = (await async_input("Satılacak tokenın mint adresini girin: ")).strip()
            if mint_address in trade_bot.positions:
                await trade_bot.close_position_manually(mint_address)
                last_action_message = f"Manuel satım başlatıldı: {mint_address}"
            else:
                last_action_message = f"❌ Belirtilen token için aktif pozisyon bulunamadı: {mint_address}"
                animated_text(last_action_message)
        except Exception as e:
            last_action_message = f"❌ Satım hatası: {e}"
            animated_text(last_action_message)
        await async_input("Devam etmek için Enter'a bas")
    
    elif choice == "11":
        await generate_daily_report(trade_bot)
        last_action_message = "Günlük rapor oluşturuldu"
        await async_input("Devam etmek için Enter'a bas")
    
    elif choice == "12":
        trade_settings["simulation_mode"] = not trade_settings["simulation_mode"]
        last_action_message = f"Simülasyon modu {'açıldı' if trade_settings['simulation_mode'] else 'kapatıldı'}"
        animated_text(last_action_message)
        await async_input("Devam etmek için Enter'a bas")
    
    elif choice == "13":
        print("\nMevcut Strateji Profilleri:", list(STRATEGY_PROFILES.keys()))
        profile = (await async_input("Strateji profilini girin (agresif, dengeli, muhafazakar): ")).strip().lower()
        if profile in STRATEGY_PROFILES:
            trade_settings.update(STRATEGY_PROFILES[profile])
            current_strategy = profile
            last_action_message = f"Strateji profili '{profile}' olarak ayarlandı"
            animated_text(last_action_message)
        else:
            last_action_message = "❌ Geçersiz strateji profili"
            animated_text(last_action_message)
        await async_input("Devam etmek için Enter'a bas")
    
    elif choice == "14":
        trade_settings["night_mode_enabled"] = not trade_settings["night_mode_enabled"]
        last_action_message = f"Gece modu {'açıldı' if trade_settings['night_mode_enabled'] else 'kapatıldı'}"
        animated_text(last_action_message)
        check_night_mode_transition()
        await async_input("Devam etmek için Enter'a bas")
    
    elif choice == "15":
        trade_settings["sniping_enabled"] = not trade_settings["sniping_enabled"]
        last_action_message = f"Sniping özelliği {'açıldı' if trade_settings['sniping_enabled'] else 'kapatıldı'}"
        animated_text(last_action_message)
        await async_input("Devam etmek için Enter'a bas")
    
    elif choice == "16":
        trade_settings["rapid_cycle_enabled"] = not trade_settings["rapid_cycle_enabled"]
        last_action_message = f"Hızlı Döngü {'açıldı' if trade_settings['rapid_cycle_enabled'] else 'kapatıldı'}"
        animated_text(last_action_message)
        
        if trade_settings["rapid_cycle_enabled"] and not trade_bot.rapid_cycle_active:
            from gotnw_tradebot.core.rapid_cycle import start_rapid_cycle
            asyncio.create_task(start_rapid_cycle(trade_bot))
        
        await async_input("Devam etmek için Enter'a bas")
    
    elif choice == "17":
        trade_settings["momentum_enabled"] = not trade_settings["momentum_enabled"]
        last_action_message = f"Momentum Tabanlı Alım {'açıldı' if trade_settings['momentum_enabled'] else 'kapatıldı'}"
        animated_text(last_action_message)
        await async_input("Devam etmek için Enter'a bas")
    
    elif choice == "18":
        trade_settings["whale_tracking_enabled"] = not trade_settings["whale_tracking_enabled"]
        last_action_message = f"Balina Takibi {'açıldı' if trade_settings['whale_tracking_enabled'] else 'kapatıldı'}"
        animated_text(last_action_message)
        await async_input("Devam etmek için Enter'a bas")
    
    elif choice == "19":
        trade_settings["volatility_trading_enabled"] = not trade_settings["volatility_trading_enabled"]
        last_action_message = f"Volatilite Tabanlı İşlem {'açıldı' if trade_settings['volatility_trading_enabled'] else 'kapatıldı'}"
        animated_text(last_action_message)
        await async_input("Devam etmek için Enter'a bas")
    
    elif choice == "20":
        trade_settings["liquidity_exit_enabled"] = not trade_settings["liquidity_exit_enabled"]
        last_action_message = f"Likidite Çıkış Stratejisi {'açıldı' if trade_settings['liquidity_exit_enabled'] else 'kapatıldı'}"
        animated_text(last_action_message)
        await async_input("Devam etmek için Enter'a bas")
    
    elif choice == "21":
        trade_settings["ai_enabled"] = not trade_settings["ai_enabled"]
        trade_settings["ai_pump_duration_prediction_enabled"] = trade_settings["ai_enabled"]
        last_action_message = f"AI Özellikleri {'açıldı' if trade_settings['ai_enabled'] else 'kapatıldı'}"
        animated_text(last_action_message)
        await async_input("Devam etmek için Enter'a bas")
    
    elif choice == "22":
        ai_options = [
            "1. AI Modellerini Eğit",
            "2. AI Modellerini Yükle",
            "3. AI Modellerini Kaydet",
            "4. AI Performans Metriklerini Göster",
            "0. Geri Dön"
        ]
        print("\nAI Model Yönetimi")
        for option in ai_options:
            print(option)
        ai_choice = (await async_input("Seçiminizi yapın (0-4): ")).strip()
        
        if ai_choice == "1":
            animated_text("AI modelleri eğitiliyor...")
            if len(trade_bot.analyzer.price_history) < 10:
                last_action_message = "❌ Eğitim için yeterli veri yok! Önce token izlemeye başlayın."
                animated_text(last_action_message)
            else:
                pump_success = trade_bot.analyzer.train_pump_detection_model()
                duration_success = trade_bot.analyzer.train_pump_duration_model()
                price_success = trade_bot.analyzer.train_price_prediction_model()
                if pump_success or duration_success or price_success:
                    last_action_message = "✅ AI modelleri başarıyla eğitildi!"
                else:
                    last_action_message = "❌ AI modelleri eğitilemedi, yeterli veri bulunamadı."
                animated_text(last_action_message)
        
        elif ai_choice == "2":
            filepath = (await async_input("Model dosya adı öneki (varsayılan: ai_models): ")).strip()
            if not filepath:
                filepath = "ai_models"
            trade_bot.analyzer.load_models(filepath)
            last_action_message = f"AI modelleri yüklendi: {filepath}"
            animated_text(last_action_message)
        
        elif ai_choice == "3":
            filepath = (await async_input("Model dosya adı öneki (varsayılan: ai_models): ")).strip()
            if not filepath:
                filepath = "ai_models"
            trade_bot.analyzer.save_models(filepath)
            last_action_message = f"AI modelleri kaydedildi: {filepath}"
            animated_text(last_action_message)
        
        elif ai_choice == "4":
            print("\nAI Model Performansı:")
            print("\nPump Detection Model:")
            precision = trade_bot.analyzer.model_metrics['pump_detection']['precision']
            recall = trade_bot.analyzer.model_metrics['pump_detection']['recall']
            f1 = trade_bot.analyzer.model_metrics['pump_detection']['f1']
            print(f"Precision: {precision:.4f}")
            print(f"Recall: {recall:.4f}")
            print(f"F1 Score: {f1:.4f}")
            
            print("\nPump Duration Model:")
            mae = trade_bot.analyzer.model_metrics['pump_duration']['mae']
            r2 = trade_bot.analyzer.model_metrics['pump_duration']['r2']
            print(f"MAE: {mae:.4f}")
            print(f"R²: {r2:.4f}")
            
            print("\nPrice Prediction Model:")
            mae = trade_bot.analyzer.model_metrics['price_prediction']['mae']
            r2 = trade_bot.analyzer.model_metrics['price_prediction']['r2']
            print(f"MAE: {mae:.4f}")
            print(f"R²: {r2:.4f}")
            
            last_action_message = "AI model performans metrikleri gösterildi"
        
        await async_input("Devam etmek için Enter'a bas")
    
    elif choice == "23":
        mint_address = (await async_input("Analiz edilecek tokenın mint adresini girin: ")).strip()
        if not mint_address:
            last_action_message = "❌ Geçerli bir mint adresi girmelisiniz"
        else:
            token_analysis = trade_bot.analyzer.analyze_token(mint_address)
            print("\n" + "=" * 50)
            print(token_analysis)
            print("=" * 50 + "\n")
            last_action_message = f"Token analiz raporu gösterildi: {mint_address}"
        await async_input("Devam etmek için Enter'a bas")
    
    elif choice == "24":
        print("GUI arayüzü başlatılıyor...")
        import threading
        from gotnw_tradebot.gui.main_window import start_gui
        threading.Thread(target=start_gui, args=(trade_bot,), daemon=True).start()
        last_action_message = "GUI arayüzü başlatıldı"
        await async_input("Devam etmek için Enter'a bas")
    
    elif choice == "25":
        from gotnw_tradebot.config import DEBUG_MODE
        DEBUG_MODE = not DEBUG_MODE
        last_action_message = f"Debug modu {'açıldı' if DEBUG_MODE else 'kapatıldı'}"
        animated_text(last_action_message)
        await async_input("Devam etmek için Enter'a bas")
    
    else:
        last_action_message = "❌ Geçersiz seçim"
        animated_text(last_action_message)
        await async_input("Devam etmek için Enter'a bas")
    
    return False


async def generate_daily_report(trade_bot):
    """
    Günlük ticaret raporunu oluşturur
    
    Args:
        trade_bot: TradeBot nesnesi
    """
    with open(DAILY_REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write(f"Günlük Rapor - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Toplam İşlem: {len(trade_bot.daily_trades)}\n")
        
        for trade in trade_bot.daily_trades:
            f.write(
                f"{trade['type'].upper()} - {trade['mint']} - {trade['amount']} SOL @ "
                f"${trade_bot.format_price(trade['price'])} - {trade['timestamp']}\n"
            )
        
        total_buy = sum(t['amount'] for t in trade_bot.daily_trades if t['type'] == 'buy')
        total_sell = sum(t['amount'] for t in trade_bot.daily_trades if t['type'] == 'sell')
        
        f.write(f"\nToplam Alım: {total_buy:.4f} SOL\n")
        f.write(f"Toplam Satım: {total_sell:.4f} SOL\n")
        
        f.write("\nMevcut Açık Pozisyonlar:\n")
        for mint, data in trade_bot.positions.items():
            f.write(f"- {mint}: {data['remaining_amount']:.4f} SOL\n")
    
    animated_text(f"📊 Günlük rapor oluşturuldu: {DAILY_REPORT_FILE}")


async def update_display(trade_bot):
    """
    Cüzdan bilgilerini ekranda gösterir
    
    Args:
        trade_bot: TradeBot nesnesi
    """
    try:
        from gotnw_tradebot.utils.formatting import print_wallet_info
        
        sol_price = await get_sol_price() or 0
        balance = await wallet_manager.get_balance()
        
        if wallet_manager.active_wallet_index == -1:
            current_wallet = "Bağlı değil"
        else:
            current_wallet = str(wallet_manager.wallets[wallet_manager.active_wallet_index]["keypair"].pubkey())
        
        print_wallet_info(current_wallet, balance, sol_price)
    
    except Exception as e:
        logger.error(f"Ekran güncelleme hatası: {e}")
# -*- coding: utf-8 -*-
import json
import base58
import os
from datetime import datetime
from solders.keypair import Keypair
import traceback
from loguru import logger

from utils.logging_utils import log_to_file
from utils.console_utils import animated_text
from config import STATE_FILE, trade_settings
import config

async def save_state(trade_bot):
    """
    Mevcut bot durumunu kaydetme fonksiyonu
    
    Args:
        trade_bot (TradeBot): Trade bot örneği
    
    Returns:
        bool: İşlem başarısı
    """
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
            "current_strategy": config.current_strategy,
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
            
        return True
    except Exception as e:
        log_to_file(f"❌ Durum kaydedilemedi: {e}")
        logger.error(f"Durum kaydedilemedi: {e}")
        traceback.print_exc()
        return False

async def load_state(trade_bot):
    """
    Kaydedilmiş bot durumunu yükleme fonksiyonu
    
    Args:
        trade_bot (TradeBot): Trade bot örneği
        
    Returns:
        bool: İşlem başarısı
    """
    try:
        # State dosyası var mı kontrol et
        if not os.path.exists(STATE_FILE):
            animated_text(f"⚠️ Kaydedilmiş durum bulunamadı, varsayılan ayarlar kullanılıyor")
            logger.warning("Durum dosyası bulunamadı")
            return False
            
        # Dosyayı aç ve oku
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            state = json.load(f)
        
        logger.info("Durum dosyası başarıyla okundu.")
        
        # Pozisyonları güncelle
        if "positions" in state:
            trade_bot.positions = state["positions"]
            
        # Ayarları güncelle
        if "settings" in state:
            config.trade_settings.update(state["settings"])
            
        # İlk görülen mint adresleri
        if "first_seen_mints" in state:
            try:
                trade_bot.first_seen_mints = {mint: datetime.strptime(ts, '%Y-%m-%d %H:%M:%S') for mint, ts in state["first_seen_mints"].items()}
            except ValueError:
                trade_bot.first_seen_mints = {mint: datetime.fromisoformat(ts) for mint, ts in state["first_seen_mints"].items()}
                                      
        # Geçmiş işlemler
        if "past_trades" in state:
            for trade in state["past_trades"]:
                if isinstance(trade["timestamp"], str):
                    try:
                        trade["timestamp"] = datetime.strptime(trade["timestamp"], '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        trade["timestamp"] = datetime.fromisoformat(trade["timestamp"])
            trade_bot.past_trades = state["past_trades"]
            
        # Aktif strateji
        if "current_strategy" in state:
            config.current_strategy = state["current_strategy"]
        
        # İşlenmiş mint adresleri
        if "processed_mints" in state:
            trade_bot.processed_mints = set(state["processed_mints"])
        
        # Cüzdan bilgilerini yükle
        if "wallets" in state and "active_wallet_index" in state:
            logger.info(f"Cüzdan verileri bulundu. Yüklenecek cüzdan sayısı: {len(state['wallets'])}")
            
            try:
                # Mevcut cüzdanları temizle
                from wallet import wallet_manager
                wallet_manager.wallets = []
                wallet_manager.active_wallet_index = -1
                
                # Cüzdanları yükle
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
                
                # Aktif cüzdanı ayarla
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
        return True
    except Exception as e:
        log_to_file(f"❌ Durum yüklenemedi: {e}")
        logger.error(f"Durum yüklenemedi: {e}")
        traceback.print_exc()
        return False
# -*- coding: utf-8 -*-
"""
Mesaj izleme modülü - yeni token mint adreslerini tespit eder
"""

import os
import json
import asyncio
from datetime import datetime
from loguru import logger

from utils.console_utils import animated_text
from config import INPUT_FILE, trade_settings
from core.websocket_manager import add_token_subscription
from utils.network_utils import get_sol_price
from utils.formatting import print_wallet_info
from wallet import wallet_manager
from utils.logging_utils import log_to_file


async def monitor_filtered_messages(trade_bot):
    """
    Yeni mesajları izler ve token alımını gerçekleştirir
    """
    last_file_mod_time = 0
    processed_message_ids = set()
    
    is_first_run = True
    
    while True:
        try:
            if os.path.exists(INPUT_FILE):
                current_file_mod_time = os.path.getmtime(INPUT_FILE)
                
                if is_first_run:
                    last_file_mod_time = current_file_mod_time
                    is_first_run = False
                    trade_bot.update_log(None, "ℹ️ İlk çalıştırma: Mevcut tokenlar izlemeye alındı, alım yapılmayacak")
                    
                    try:
                        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
                            messages = json.load(f)
                        
                        for message in messages:
                            if 'mint_address' in message and message['mint_address']:
                                mint_address = message['mint_address']
                                
                                if mint_address not in trade_bot.processed_mints:
                                    trade_bot.processed_mints.add(mint_address)
                                    message_id = message.get('id', str(hash(json.dumps(message, sort_keys=True))))
                                    processed_message_ids.add(message_id)
                                    
                                    await add_token_subscription(trade_bot, mint_address)
                        
                        trade_bot.update_log(None, f"ℹ️ Toplam {len(trade_bot.processed_mints)} token izlemeye alındı")
                    except Exception as e:
                        trade_bot.update_log(None, f"❌ İlk çalıştırma tokenları işleme hatası: {e}")
                    
                    await asyncio.sleep(2)
                    continue
                
                if current_file_mod_time > last_file_mod_time:
                    animated_text("Yeni mesajlar tespit edildi, işleniyor...")
                    try:
                        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
                            messages = json.load(f)
                        
                        new_messages_processed = 0
                        for message in messages:
                            message_id = message.get('id', str(hash(json.dumps(message, sort_keys=True))))
                            if message_id in processed_message_ids:
                                continue
                            
                            if 'mint_address' in message and message['mint_address']:
                                mint_address = message['mint_address']
                                
                                if mint_address not in trade_bot.processed_mints:
                                    trade_bot.processed_mints.add(mint_address)
                                    processed_message_ids.add(message_id)
                                    
                                    await add_token_subscription(trade_bot, mint_address)
                                    trade_bot.update_log(mint_address, f"Yeni token eklendi: {mint_address}")
                                    new_messages_processed += 1
                        
                        trade_bot.update_log(None, f"ℹ️ {new_messages_processed} yeni token işlendi")
                        last_file_mod_time = current_file_mod_time
                    except Exception as e:
                        trade_bot.update_log(None, f"❌ Yeni mesajları işleme hatası: {e}")
                
                await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Mesaj izleme hatası: {e}")
            await asyncio.sleep(2)

async def auto_clear_console(trade_bot):
    """
    Konsolu düzenli aralıklarla temizler ve cüzdan bilgilerini gösterir
    
    Args:
        trade_bot: TradeBot nesnesi
    """
    while True:
        try:
            # SOL fiyatını al
            sol_price = await get_sol_price() or 0
            
            # Bakiyeyi al
            balance = await wallet_manager.get_balance()
            
            # Aktif cüzdan adresini al
            current_wallet = "Bağlı değil"
            if (wallet_manager.active_wallet_index >= 0 and 
                len(wallet_manager.wallets) > wallet_manager.active_wallet_index):
                current_wallet = str(wallet_manager.wallets[wallet_manager.active_wallet_index]["keypair"].pubkey())
            
            # Ekran bilgilerini güncelle
            print_wallet_info(current_wallet, balance, sol_price)
            
            # 10 dakikada bir çalış
            await asyncio.sleep(600)
        
        except Exception as e:
            # Herhangi bir hata durumunda logla ve devam et
            log_to_file(f"Otomatik konsol temizleme hatası: {e}")
            await asyncio.sleep(600)
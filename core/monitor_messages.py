# -*- coding: utf-8 -*-
"""
Mesaj izleme modülü - yeni token mint adreslerini tespit eder
"""

import os
import json
import asyncio
from datetime import datetime
from loguru import logger

from gotnw_tradebot.utils.console_utils import animated_text
from gotnw_tradebot.config import INPUT_FILE, trade_settings
from gotnw_tradebot.core.websocket_manager import add_token_subscription


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
                    animated_text
# -*- coding: utf-8 -*-
"""
WebSocket yönetim modülü - token fiyat verilerini asenkron olarak işler
"""

import asyncio
import json
import websockets
import base64
from datetime import datetime
from loguru import logger

from utils.logging_utils import log_to_file
from config import HELIUS_WS_URL


async def start_enhanced_websocket(trade_bot):
    """
    Helius Enhanced WebSocket bağlantısını başlatır ve yönetir
    
    Args:
        trade_bot: TradeBot nesnesi
    """
    uri = HELIUS_WS_URL
    api_key = uri.split("api-key=")[1] if "api-key=" in uri else "92cbc54b-c8e5-4de4-ac41-a4fcffc600e4"
    
    trade_bot.websocket_active = True
    max_retries = 5
    retry_count = 0
    
    while trade_bot.websocket_active and retry_count < max_retries:
        try:
            async with websockets.connect(uri) as websocket:
                trade_bot.websocket = websocket
                logger.info(f"WebSocket bağlantısı kuruldu, {len(trade_bot.subscribed_tokens)} token abone oluyor...")
                
                subscription_msg = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "subscribeEnhancedTransactions",
                    "params": {
                        "tokens": list(trade_bot.subscribed_tokens),
                        "channels": ["prices", "transfers", "metadata", "whale_transactions"],
                        "apiKey": api_key
                    }
                }
                
                await websocket.send(json.dumps(subscription_msg))
                logger.info("Token abonelik isteği gönderildi")
                
                while trade_bot.websocket_active:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=30)
                        message_data = json.loads(message)
                        
                        if message_data.get('method') == 'enhancedTransactionUpdate':
                            await _process_enhanced_transaction(trade_bot, message_data.get('params', {}))
                        elif message_data.get('method') == 'tokenPriceUpdate':
                            await _process_token_price_update(trade_bot, message_data.get('params', {}))
                        elif message_data.get('method') == 'whaleTransactionDetected':
                            await _process_whale_transaction(trade_bot, message_data.get('params', {}))
                        
                    except asyncio.TimeoutError:
                        ping_msg = {"jsonrpc": "2.0", "id": 9999, "method": "ping"}
                        await websocket.send(json.dumps(ping_msg))
                        continue
                    except Exception as msg_error:
                        logger.error(f"WebSocket mesaj işleme hatası: {msg_error}")
                        log_to_file(f"WebSocket mesaj hatası: {msg_error}")
                        continue
                        
        except websockets.exceptions.ConnectionClosed:
            logger.warning(f"WebSocket bağlantısı kapandı, yeniden bağlanılıyor... ({retry_count + 1}/{max_retries})")
            retry_count += 1
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"WebSocket genel hatası: {e}")
            log_to_file(f"WebSocket hatası: {e}")
            retry_count += 1
            await asyncio.sleep(2)
            
    logger.warning("WebSocket bağlantısı kurulamadı, periyodik güncellemeye geçiliyor...")
    asyncio.create_task(update_prices_periodically(trade_bot))


async def _process_enhanced_transaction(trade_bot, transaction_data):
    """
    Gelişmiş işlem verilerini işler
    
    Args:
        trade_bot: TradeBot nesnesi
        transaction_data (dict): İşlem verileri
    """
    mint_address = transaction_data.get('token')
    transaction_details = transaction_data.get('transaction')
    
    if not mint_address or not transaction_details:
        return
    
    await _analyze_transaction_details(trade_bot, mint_address, transaction_details)


async def _process_token_price_update(trade_bot, price_data):
    """
    Token fiyat güncellemelerini işler
    
    Args:
        trade_bot: TradeBot nesnesi
        price_data (dict): Fiyat verileri
    """
    mint_address = price_data.get('token')
    price = price_data.get('price')
    
    if mint_address and price:
        current_price = float(price)
        old_price = trade_bot.websocket_prices.get(mint_address)
        
        trade_bot.websocket_prices[mint_address] = current_price
        
        current_time = datetime.now()
        trade_bot.price_history[mint_address].append({
            "timestamp": current_time, 
            "price_usd": current_price
        })
        
        trade_bot.analyzer.update_price_history(mint_address, current_price, current_time)
        
        if mint_address not in trade_bot.initial_prices:
            trade_bot.initial_prices[mint_address] = current_price
            trade_bot.first_seen_mints[mint_address] = current_time
            trade_bot.update_log(
                mint_address,
                f"ℹ️ {mint_address} için çıkış fiyatı: ${trade_bot.format_price(current_price)}"
            )
        
        if mint_address in trade_bot.trade_windows and old_price != current_price:
            def update_price_in_window():
                try:
                    if mint_address in trade_bot.positions:
                        data = trade_bot.positions[mint_address]
                        buy_price = data.get("buy_price", 0)
                        
                        trade_bot.websocket_prices[mint_address] = current_price
                        
                        if buy_price > 0:
                            profit_loss = ((current_price - buy_price) / buy_price) * 100
                            if abs(profit_loss) >= 0.5:
                                trade_bot.update_log(
                                    mint_address,
                                    f"🔄 Fiyat Güncellendi: ${trade_bot.format_price(current_price)} ({'+' if profit_loss > 0 else ''}{profit_loss:.2f}%)"
                                )
                except Exception as e:
                    log_to_file(f"WebSocket fiyat güncelleme hatası: {e}")
            
            if trade_bot.root and trade_bot.root.winfo_exists():
                trade_bot.root.after(0, update_price_in_window)
                    
        if trade_bot.config.trade_settings["rapid_cycle_enabled"] and old_price and old_price > 0:
            price_change_pct = ((current_price - old_price) / old_price) * 100
            
            if (trade_bot.config.trade_settings["micro_pump_detection_enabled"] and
                price_change_pct >= trade_bot.config.trade_settings["micro_pump_threshold"]):
                trade_bot.update_log(
                    mint_address,
                    f"Mikro Pump Tespit Edildi: {mint_address} - %{price_change_pct:.2f} artış"
                )
                if (mint_address not in trade_bot.positions and
                    mint_address not in trade_bot.pending_buys and
                    trade_bot.config.trade_settings["autobuy_enabled"]):
                    if trade_bot.config.trade_settings["ai_pump_duration_prediction_enabled"]:
                        momentum = trade_bot.analyzer.calculate_momentum(mint_address)
                        volatility = trade_bot.analyzer.calculate_volatility(mint_address)
                        volume = 0
                        predicted_duration = trade_bot.analyzer.predict_pump_duration(
                            mint_address, momentum, volatility, volume
                        )
                        trade_bot.update_log(
                            mint_address,
                            f"Pump Süresi Tahmini: {predicted_duration} saniye"
                        )
                        trade_bot.pump_start_times[mint_address] = current_time
                        trade_bot.pending_buys.add(mint_address)
                        asyncio.create_task(
                            trade_bot.buy(
                                mint_address,
                                detection_time=current_time,
                                manual=False,
                                pump_detected=True
                            )
                        )


async def _process_whale_transaction(trade_bot, whale_data):
    """
    Balina işlemlerini işler
    
    Args:
        trade_bot: TradeBot nesnesi
        whale_data (dict): Balina işlem verileri
    """
    mint_address = whale_data.get('token')
    transaction_details = whale_data.get('transaction')
    
    if mint_address and transaction_details:
        await _analyze_transaction_details(trade_bot, mint_address, transaction_details)


async def _analyze_transaction_details(trade_bot, mint_address, transaction_details):
    """
    Gelişmiş işlem detaylarını analiz eder
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address (str): Token mint adresi
        transaction_details (dict): İşlem detayları
    """
    if not transaction_details:
        return
    
    native_transfers = transaction_details.get('nativeTransfers', [])
    token_transfers = transaction_details.get('tokenTransfers', [])
    
    whale_transfers = [
        transfer for transfer in native_transfers 
        if float(transfer.get('amount', 0)) >= trade_bot.config.trade_settings.get("whale_threshold_sol", 5)
    ]
    
    if whale_transfers:
        trade_bot.update_log(
            mint_address, 
            f"Balina İşlemi Tespit Edildi: {len(whale_transfers)} transfer"
        )
        
        if trade_bot.config.trade_settings["whale_tracking_enabled"]:
            await _handle_whale_trade_strategy(trade_bot, mint_address, whale_transfers)


async def _handle_whale_trade_strategy(trade_bot, mint_address, whale_transfers):
    """
    Balina işlemlerine göre ticaret stratejisi uygular
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address (str): Token mint adresi
        whale_transfers (list): Balina transfer listesi
    """
    pass


async def add_token_subscription(trade_bot, mint_address):
    """
    WebSocket'e yeni bir token ekler
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address (str): Token mint adresi
    """
    try:
        if mint_address not in trade_bot.subscribed_tokens:
            trade_bot.subscribed_tokens.add(mint_address)
            trade_bot.update_log(
                mint_address,
                f"ℹ️ Yeni token eklendi: {mint_address}. Çıkış fiyatı bekleniyor..."
            )
            if not trade_bot.websocket_active:
                await asyncio.wait_for(start_enhanced_websocket(trade_bot), timeout=10)
            
            if trade_bot.websocket:
                api_key = "92cbc54b-c8e5-4de4-ac41-a4fcffc600e4"
                subscription_msg = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "subscribeEnhancedTransactions",
                    "params": {
                        "tokens": [mint_address],
                        "channels": ["prices", "transfers", "metadata", "whale_transactions"],
                        "apiKey": api_key
                    }
                }
                await trade_bot.websocket.send(json.dumps(subscription_msg))
    except asyncio.TimeoutError:
        trade_bot.update_log(mint_address, "❌ WebSocket zaman aşımı, işlem devam ediyor...")
    except Exception as e:
        trade_bot.update_log(mint_address, f"WebSocket token ekleme hatası: {e}")


async def update_prices_periodically(trade_bot, interval=10):
    """
    Periyodik olarak fiyatları günceller (WebSocket bağlantısı yoksa)
    
    Args:
        trade_bot: TradeBot nesnesi
        interval (int): Güncelleme aralığı (saniye)
    """
    from core.price_manager import get_token_info
    
    while trade_bot.websocket_active:
        for mint_address in trade_bot.subscribed_tokens:
            try:
                token_info = await get_token_info(trade_bot, mint_address, force_update=True)
                if token_info:
                    old_price = trade_bot.websocket_prices.get(mint_address)
                    current_price = token_info["price_usd"]
                    current_time = datetime.now()
                    trade_bot.websocket_prices[mint_address] = current_price
                    trade_bot.price_history[mint_address].append(
                        {"timestamp": current_time, "price_usd": current_price}
                    )
                    trade_bot.analyzer.update_price_history(mint_address, current_price, current_time)
                    trade_bot.analyzer.update_volume_history(
                        mint_address, token_info.get("volume", 0), current_time
                    )
                    trade_bot.analyzer.update_liquidity_history(
                        mint_address, token_info.get("liquidity_usd", 0), current_time
                    )
                    if trade_bot.config.trade_settings["rapid_cycle_enabled"] and old_price and old_price > 0:
                        price_change_pct = ((current_price - old_price) / old_price) * 100
                        from core.trade_analyzer import analyze_token_dynamics
                        await analyze_token_dynamics(
                            trade_bot, mint_address, current_price, token_info, price_change_pct
                        )
            except Exception as e:
                trade_bot.update_log(
                    mint_address,
                    f"Fiyat güncelleme hatası: {mint_address}, Hata: {e}"
                )
        await asyncio.sleep(interval)
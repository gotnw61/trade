# -*- coding: utf-8 -*-
"""
Hızlı döngü modülü - kısa aralıklarla token fiyatlarını izler
"""

import asyncio
import time
from datetime import datetime
from loguru import logger

from core.price_manager import get_token_info, get_token_price
from core.trade_analyzer import analyze_token_dynamics


async def start_rapid_cycle(trade_bot):
    """
    Hızlı döngü modunu başlatır ve yönetir
    
    Args:
        trade_bot: TradeBot nesnesi
    """
    trade_bot.rapid_cycle_active = True
    interval = trade_bot.config.trade_settings["rapid_cycle_interval"]
    
    logger.info(f"Hızlı döngü başlatıldı, interval: {interval}s")
    
    while trade_bot.rapid_cycle_active:
        for mint_address in list(trade_bot.subscribed_tokens):
            if mint_address in trade_bot.last_rapid_cycle:
                last_time = trade_bot.last_rapid_cycle[mint_address]
                if (datetime.now() - last_time).total_seconds() < interval:
                    continue
            try:
                token_info = await get_token_info(trade_bot, mint_address, force_update=True)
                if token_info:
                    current_price = token_info["price_usd"]
                    current_time = datetime.now()
                    old_price = trade_bot.websocket_prices.get(mint_address)
                    trade_bot.websocket_prices[mint_address] = current_price
                    trade_bot.last_rapid_cycle[mint_address] = current_time
                    trade_bot.analyzer.update_price_history(mint_address, current_price, current_time)
                    trade_bot.analyzer.update_volume_history(
                        mint_address, token_info.get("volume", 0), current_time
                    )
                    trade_bot.analyzer.update_liquidity_history(
                        mint_address, token_info.get("liquidity_usd", 0), current_time
                    )
                    if old_price and old_price > 0:
                        price_change_pct = ((current_price - old_price) / old_price) * 100
                        await analyze_token_dynamics(
                            trade_bot, mint_address, current_price, token_info, price_change_pct
                        )
            except Exception as e:
                # Sessiz başarısızlık - hata loglamayı azalt
                pass
        await asyncio.sleep(interval)
    
    logger.info("Hızlı döngü durduruldu")


async def detect_micro_pumps(trade_bot, mint_address, current_price, old_price):
    """
    Mikro pump'ları tespit eder
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address (str): Token mint adresi
        current_price (float): Güncel fiyat
        old_price (float): Önceki fiyat
        
    Returns:
        tuple: (pump tespit edildi mi, pump yüzdesi)
    """
    if not old_price or old_price <= 0:
        return False, 0
    
    price_change_pct = ((current_price - old_price) / old_price) * 100
    threshold = trade_bot.config.trade_settings["micro_pump_threshold"]
    
    is_micro_pump = price_change_pct >= threshold
    
    if is_micro_pump:
        trade_bot.update_log(
            mint_address, 
            f"🔥 Mikro Pump Tespit Edildi: {mint_address} - %{price_change_pct:.2f} artış"
        )
        
        # Pump sinyali gönderme
        if trade_bot.analyzer:
            trade_bot.analyzer.record_pump_event(
                mint_address, 
                current_price, 
                old_price, 
                price_change_pct
            )
    
    return is_micro_pump, price_change_pct


async def predict_pump_duration(trade_bot, mint_address):
    """
    Pump süresini tahmin eder (AI tabanlı)
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address (str): Token mint adresi
        
    Returns:
        int: Tahmini pump süresi (saniye)
    """
    if not trade_bot.analyzer or not hasattr(trade_bot.analyzer, 'predict_pump_duration'):
        return 60  # Varsayılan süre
    
    momentum = trade_bot.analyzer.calculate_momentum(mint_address)
    volatility = trade_bot.analyzer.calculate_volatility(mint_address)
    volume = 0
    
    try:
        current_price = await get_token_price(trade_bot, mint_address)
        token_info = await get_token_info(trade_bot, mint_address)
        if token_info:
            volume = token_info.get("volume", 0)
    except:
        pass
    
    # AI tabanlı pump süresi tahmini
    predicted_duration = trade_bot.analyzer.predict_pump_duration(
        mint_address, momentum, volatility, volume
    )
    
    # Min/max sınırları uygula
    min_duration = trade_bot.config.trade_settings.get("min_pump_duration_seconds", 60)
    max_duration = 300  # 5 dakika
    
    return max(min_duration, min(predicted_duration, max_duration))
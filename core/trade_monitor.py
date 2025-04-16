# -*- coding: utf-8 -*-
"""
İşlem izleme modülü
"""

import asyncio
import time
from loguru import logger

from gotnw_tradebot.config import trade_settings
from gotnw_tradebot.core.price_manager import get_token_price
from gotnw_tradebot.core.sell_logic import (
    process_stop_loss, process_take_profit, process_trailing_stop_loss,
    process_time_based_close
)
from gotnw_tradebot.utils.logging_utils import log_to_file


async def monitor_positions(trade_bot):
    """
    Açık pozisyonları sürekli olarak izler ve TP/SL kontrollerini yapar.
    
    Args:
        trade_bot: TradeBot nesnesi
    """
    last_check = {}
    
    while True:
        try:
            if not trade_settings["autosell_enabled"]:
                await asyncio.sleep(5)
                continue
            
            current_time = time.time()
            tasks = []
            
            for mint_address in list(trade_bot.positions.keys()):
                # Her token için en az 1 saniye geçmesini bekle
                if mint_address in last_check and current_time - last_check[mint_address] < 1:
                    continue
                
                last_check[mint_address] = current_time
                tasks.append(check_position(trade_bot, mint_address))
            
            if tasks:
                await asyncio.gather(*tasks)
                
            # Hızlı döngü kontrolü
            interval = trade_settings.get("rapid_cycle_interval", 0.5)
            if trade_settings.get("rapid_cycle_enabled", False) and not trade_bot.rapid_cycle_active:
                trade_bot.rapid_cycle_active = True
                asyncio.create_task(trade_bot.start_rapid_cycle())
            elif not trade_settings.get("rapid_cycle_enabled", False) and trade_bot.rapid_cycle_active:
                trade_bot.rapid_cycle_active = False
                
            await asyncio.sleep(interval)
            
        except Exception as e:
            log_to_file(f"Pozisyon izleme hatası: {e}")
            await asyncio.sleep(5)


async def check_position(trade_bot, mint_address):
    """
    Belirli bir pozisyonu kontrol eder ve TP/SL kurallarını uygular.
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address: Token mint adresi
    """
    try:
        data = trade_bot.positions.get(mint_address)
        if not data:
            return
            
        current_price = await get_token_price(trade_bot, mint_address, force_update=True)
        if current_price is None:
            trade_bot.update_log(mint_address, f"❌ {mint_address} için fiyat alınamadı, kontrol atlandı.")
            return
        
        # En yüksek fiyatı güncelle
        data["highest_price"] = max(data["highest_price"], current_price)
        
        # Zamanı kontrol et
        start_time = trade_bot.trade_start_times.get(mint_address)
        
        if start_time:
            elapsed_seconds = (asyncio.get_event_loop().time() - start_time.timestamp())
            
            # 20 saniyelik süre kontrolü (Debug için)
            if 19 <= elapsed_seconds <= 21:
                price_change = ((current_price - data["buy_price"]) / data["buy_price"]) * 100
                trade_bot.update_log(mint_address, 
                    f"⏱️ Zaman kontrolü: {elapsed_seconds:.1f}s, Fiyat değişimi: {price_change:.2f}%"
                )
                if data["tp_levels"]:
                    min_tp = min([level["profit"] for level in data["tp_levels"]])
                    trade_bot.update_log(mint_address, 
                        f"ℹ️ İlk TP hedefi: {min_tp}%, Mevcut: {price_change:.2f}%"
                    )
        
        # Zaman bazlı kapanış kontrolü
        if await process_time_based_close(trade_bot, mint_address, current_price):
            return
            
        # Trailing Stop-Loss kontrolü
        if await process_trailing_stop_loss(trade_bot, mint_address, current_price):
            return
            
        # Stop-Loss kontrolü
        if await process_stop_loss(trade_bot, mint_address, current_price):
            return
            
        # Take-Profit kontrolü
        if await process_take_profit(trade_bot, mint_address, current_price):
            return
            
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Pozisyon kontrol hatası: {mint_address}\n{error_details}")
        trade_bot.update_log(mint_address, f"Pozisyon kontrol hatası: {mint_address}, Hata: {e}")


async def calculate_position_metrics(trade_bot, mint_address):
    """
    Pozisyon metriklerini hesaplar.
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address: Token mint adresi
        
    Returns:
        dict: Pozisyon metrikleri
    """
    data = trade_bot.positions.get(mint_address)
    if not data:
        return None
        
    current_price = await get_token_price(trade_bot, mint_address, force_update=True)
    if current_price is None:
        return None
        
    buy_price = data["buy_price"]
    highest_price = data["highest_price"]
    remaining_amount = data["remaining_amount"]
    total_amount = data["amount"]
    
    price_change_pct = ((current_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0
    max_price_change_pct = ((highest_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0
    drawdown_pct = ((highest_price - current_price) / highest_price) * 100 if highest_price > 0 else 0
    
    profit_loss = (current_price - buy_price) * data["remaining_token_amount"]
    percent_sold = 100 - (remaining_amount / total_amount * 100) if total_amount > 0 else 0
    
    return {
        "mint_address": mint_address,
        "buy_price": buy_price,
        "current_price": current_price,
        "highest_price": highest_price,
        "remaining_amount": remaining_amount,
        "total_amount": total_amount,
        "price_change_pct": price_change_pct,
        "max_price_change_pct": max_price_change_pct,
        "drawdown_pct": drawdown_pct,
        "profit_loss": profit_loss,
        "percent_sold": percent_sold
    }


async def get_all_positions_status(trade_bot):
    """
    Tüm pozisyonların durumunu getirir.
    
    Args:
        trade_bot: TradeBot nesnesi
        
    Returns:
        list: Pozisyon durumları listesi
    """
    results = []
    
    for mint_address in list(trade_bot.positions.keys()):
        metrics = await calculate_position_metrics(trade_bot, mint_address)
        if metrics:
            results.append(metrics)
            
    return results


async def get_portfolio_metrics(trade_bot):
    """
    Portföy metriklerini hesaplar.
    
    Args:
        trade_bot: TradeBot nesnesi
        
    Returns:
        dict: Portföy metrikleri
    """
    positions_status = await get_all_positions_status(trade_bot)
    
    total_value = sum(pos["remaining_amount"] for pos in positions_status)
    total_profit_loss = sum(pos["profit_loss"] for pos in positions_status)
    avg_profit_pct = sum(pos["price_change_pct"] for pos in positions_status) / len(positions_status) if positions_status else 0
    
    profitable_positions = sum(1 for pos in positions_status if pos["price_change_pct"] > 0)
    loss_positions = sum(1 for pos in positions_status if pos["price_change_pct"] <= 0)
    
    # Geçmiş işlemlerden metrikler
    from gotnw_tradebot.utils.trade_utils import generate_trade_analysis
    trade_analysis = generate_trade_analysis(trade_bot.past_trades)
    
    return {
        "total_positions": len(positions_status),
        "total_value": total_value,
        "total_profit_loss": total_profit_loss,
        "avg_profit_pct": avg_profit_pct,
        "profitable_positions": profitable_positions,
        "loss_positions": loss_positions,
        "past_trades_count": trade_analysis["total_trades"],
        "past_trades_profit": trade_analysis["total_profit"],
        "past_trades_success_rate": trade_analysis["success_rate"]
    }
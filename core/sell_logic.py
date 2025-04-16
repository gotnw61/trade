# -*- coding: utf-8 -*-
"""
Satım işlemleri mantığı modülü
"""

import asyncio
import traceback
from datetime import datetime

from loguru import logger

from gotnw_tradebot.config import trade_settings
from gotnw_tradebot.core.trade_executor import execute_swap
from gotnw_tradebot.core.price_manager import get_token_price, get_token_info
from gotnw_tradebot.core.trade_window import close_trade_window
from gotnw_tradebot.utils.formatting import format_price
from gotnw_tradebot.utils.logging_utils import log_to_file


async def check_stop_loss(trade_bot, mint_address, current_price):
    """
    Stop loss kontrolü yapar.
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address: Token mint adresi
        current_price: Güncel fiyat
    
    Returns:
        bool: Stop loss tetiklendiyse True, değilse False
    """
    if mint_address not in trade_bot.positions:
        return False
        
    data = trade_bot.positions[mint_address]
    buy_price = data["buy_price"]
    
    if buy_price <= 0:
        return False
        
    price_change = ((current_price - buy_price) / buy_price) * 100
    
    for level in sorted(data["sl_levels"], key=lambda x: x["loss"]):
        if price_change <= level["loss"] and data["remaining_amount"] > 0:
            return True
            
    return False


async def check_take_profit(trade_bot, mint_address, current_price):
    """
    Take profit kontrolü yapar.
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address: Token mint adresi
        current_price: Güncel fiyat
    
    Returns:
        bool: Take profit tetiklendiyse True, değilse False
    """
    if mint_address not in trade_bot.positions:
        return False
        
    data = trade_bot.positions[mint_address]
    buy_price = data["buy_price"]
    
    if buy_price <= 0:
        return False
        
    price_change = ((current_price - buy_price) / buy_price) * 100
    
    for level in sorted(data["tp_levels"], key=lambda x: x["profit"]):
        if price_change >= level["profit"] and data["remaining_amount"] > 0:
            return True
            
    return False


async def check_trailing_stop_loss(trade_bot, mint_address, current_price):
    """
    Trailing stop loss kontrolü yapar.
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address: Token mint adresi
        current_price: Güncel fiyat
    
    Returns:
        bool: Trailing stop loss tetiklendiyse True, değilse False
    """
    if mint_address not in trade_bot.positions:
        return False
        
    data = trade_bot.positions[mint_address]
    highest_price = data["highest_price"]
    
    if highest_price <= 0:
        return False
        
    trailing_drop = ((highest_price - current_price) / highest_price) * 100
    
    return trailing_drop >= trade_settings["trailing_stop_loss"] and data["remaining_amount"] > 0


async def check_time_based_close(trade_bot, mint_address, current_price):
    """
    Zaman bazlı kapanış kontrolü yapar.
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address: Token mint adresi
        current_price: Güncel fiyat
    
    Returns:
        bool: Zaman bazlı kapanış tetiklendiyse True, değilse False
    """
    if mint_address not in trade_bot.positions or mint_address not in trade_bot.trade_start_times:
        return False
        
    data = trade_bot.positions[mint_address]
    start_time = trade_bot.trade_start_times[mint_address]
    elapsed_seconds = (datetime.now() - start_time).total_seconds()
    
    if elapsed_seconds >= 20 and data["remaining_amount"] > 0 and data["tp_levels"]:
        min_tp_profit = min(level["profit"] for level in data["tp_levels"])
        buy_price = data["buy_price"]
        
        if buy_price <= 0:
            return False
            
        price_change = ((current_price - buy_price) / buy_price) * 100
        
        return price_change < min_tp_profit
    
    return False


async def process_stop_loss(trade_bot, mint_address, current_price):
    """
    Stop loss işlemini gerçekleştirir.
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address: Token mint adresi
        current_price: Güncel fiyat
    
    Returns:
        bool: İşlem başarısı
    """
    data = trade_bot.positions[mint_address]
    buy_price = data["buy_price"]
    price_change = ((current_price - buy_price) / buy_price) * 100
    
    for level in sorted(data["sl_levels"], key=lambda x: x["loss"]):
        if price_change <= level["loss"] and data["remaining_amount"] > 0:
            reason = f"Stop Loss ({level['loss']}% kaybında %{level['sell_percentage']} satış)"
            sell_amount = data["remaining_amount"] * (level["sell_percentage"] / 100)
            
            success, tx_hash = await process_sell_transaction(
                trade_bot, mint_address, sell_amount, current_price, reason)
                
            return success
                
    return False


async def process_take_profit(trade_bot, mint_address, current_price):
    """
    Take profit işlemini gerçekleştirir.
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address: Token mint adresi
        current_price: Güncel fiyat
    
    Returns:
        bool: İşlem başarısı
    """
    data = trade_bot.positions[mint_address]
    buy_price = data["buy_price"]
    price_change = ((current_price - buy_price) / buy_price) * 100
    
    for level in sorted(data["tp_levels"], key=lambda x: x["profit"]):
        if price_change >= level["profit"] and data["remaining_amount"] > 0:
            reason = f"Take Profit ({level['profit']}% kârda %{level['sell_percentage']} satış)"
            sell_amount = data["remaining_amount"] * (level["sell_percentage"] / 100)
            
            success, tx_hash = await process_sell_transaction(
                trade_bot, mint_address, sell_amount, current_price, reason)
                
            return success
                
    return False


async def process_trailing_stop_loss(trade_bot, mint_address, current_price):
    """
    Trailing stop loss işlemini gerçekleştirir.
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address: Token mint adresi
        current_price: Güncel fiyat
        
    Returns:
        bool: İşlem başarısı
    """
    if await check_trailing_stop_loss(trade_bot, mint_address, current_price):
        data = trade_bot.positions[mint_address]
        reason = f"Trailing Stop-Loss (%{trade_settings['trailing_stop_loss']} düşüş)"
        sell_amount = data["remaining_amount"]
        
        success, tx_hash = await process_sell_transaction(
            trade_bot, mint_address, sell_amount, current_price, reason)
            
        return success
            
    return False


async def process_time_based_close(trade_bot, mint_address, current_price):
    """
    Zaman bazlı kapanış işlemini gerçekleştirir.
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address: Token mint adresi
        current_price: Güncel fiyat
        
    Returns:
        bool: İşlem başarısı
    """
    if await check_time_based_close(trade_bot, mint_address, current_price):
        data = trade_bot.positions[mint_address]
        min_tp_profit = min(level["profit"] for level in data["tp_levels"])
        reason = f"Zaman Bazlı Kapatma (20 saniye içinde TP %{min_tp_profit}'ye ulaşılmadı)"
        sell_amount = data["remaining_amount"]
        
        success, tx_hash = await process_sell_transaction(
            trade_bot, mint_address, sell_amount, current_price, reason)
            
        return success
            
    return False


async def take_partial_profit(trade_bot, mint_address, percentage, reason):
    """
    Kısmi kâr alma işlemini gerçekleştirir.
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address: Token mint adresi
        percentage: Satış yüzdesi
        reason: Satış nedeni
        
    Returns:
        bool: İşlem başarısı
    """
    if mint_address not in trade_bot.positions:
        return False
        
    data = trade_bot.positions[mint_address]
    sell_amount = data["remaining_amount"] * (percentage / 100)
    
    if sell_amount <= 0:
        return False
        
    trade_bot.update_log(
        mint_address,
        f"Kısmi Kâr Alma ({reason}): {mint_address} - {percentage}% ({sell_amount} SOL) satılıyor"
    )
    
    current_price = await get_token_price(trade_bot, mint_address, force_update=True)
    if not current_price:
        trade_bot.update_log(mint_address, "❌ Fiyat alınamadı, işlem iptal edildi")
        return False
        
    success, tx_hash = await process_sell_transaction(
        trade_bot, mint_address, sell_amount, current_price, f"Kısmi Kâr Alma - {reason}")
        
    return success


async def emergency_sell(trade_bot, mint_address, reason):
    """
    Acil durum satışı gerçekleştirir.
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address: Token mint adresi
        reason: Satış nedeni
        
    Returns:
        bool: İşlem başarısı
    """
    if mint_address not in trade_bot.positions:
        return False
        
    data = trade_bot.positions[mint_address]
    sell_amount = data["remaining_amount"]
    
    trade_bot.update_log(
        mint_address,
        f"Acil Satış ({reason}): {mint_address} - {sell_amount} SOL satılıyor"
    )
    
    current_price = await get_token_price(trade_bot, mint_address, force_update=True)
    if not current_price:
        trade_bot.update_log(mint_address, "❌ Fiyat alınamadı, işlem iptal edildi")
        return False
        
    success, tx_hash = await process_sell_transaction(
        trade_bot, mint_address, sell_amount, current_price, reason)
        
    return success


async def close_position_manually(trade_bot, mint_address):
    """
    Pozisyonu manuel olarak kapatır.
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address: Token mint adresi
        
    Returns:
        bool: İşlem başarısı
    """
    if mint_address in trade_bot.positions:
        data = trade_bot.positions[mint_address]
        sell_amount = data["remaining_amount"]
        current_price = await get_token_price(trade_bot, mint_address, force_update=True)

        if current_price:
            initial_content = (
                f"ℹ️ Manuel Pozisyon Kapatma Başlatılıyor\nMint: {mint_address}\n"
                f"Miktar: {sell_amount} SOL\nFiyat: ${format_price(current_price)}"
            )
            trade_bot.update_log(mint_address, "ℹ️ İşlem penceresi açılıyor...")
            
            if mint_address not in trade_bot.trade_windows:
                from gotnw_tradebot.core.trade_window import open_trade_window
                open_trade_window(trade_bot, mint_address, "Satım", initial_content)
                trade_bot.update_log(mint_address, "ℹ️ İşlem penceresi başlatıldı")

            success, tx_hash = await process_sell_transaction(
                trade_bot, mint_address, sell_amount, current_price, "Manuel Kapatma ('q')")
                
            return success
            
        return False
        
    return False


async def process_sell_transaction(trade_bot, mint_address, sell_amount, current_price, reason):
    """
    Satım işlemini gerçekleştirir.
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address: Token mint adresi
        sell_amount: Satış miktarı
        current_price: Güncel fiyat
        reason: Satış nedeni
        
    Returns:
        tuple: (işlem başarısı, işlem hash'i)
    """
    try:
        tx_hash = await execute_swap(trade_bot, mint_address, sell_amount, buy=False)
        
        if tx_hash:
            data = trade_bot.positions[mint_address]
            
            # Kısmi satış ise pozisyonu güncelle
            if sell_amount < data["remaining_amount"]:
                percentage = sell_amount / data["remaining_amount"]
                data["remaining_amount"] -= sell_amount
                data["remaining_token_amount"] -= data["remaining_token_amount"] * percentage
                
                trade_bot.update_log(
                    mint_address,
                    f"✅ {reason}: {mint_address} - {sell_amount} SOL satıldı, "
                    f"Fiyat: ${format_price(current_price)}, TX: {tx_hash}"
                )
                
                trade_bot.past_trades.append({
                    "mint": mint_address,
                    "symbol": (await get_token_info(trade_bot, mint_address))["symbol"],
                    "buy_price": data["buy_price"],
                    "sell_price": current_price,
                    "profit_loss": (current_price - data["buy_price"]) * sell_amount,
                    "amount": sell_amount,
                    "timestamp": datetime.now(),
                    "reason": reason
                })
                
            # Tam satış ise pozisyonu kapat
            else:
                trade_bot.past_trades.append({
                    "mint": mint_address,
                    "symbol": (await get_token_info(trade_bot, mint_address))["symbol"],
                    "buy_price": data["buy_price"],
                    "sell_price": current_price,
                    "profit_loss": (current_price - data["buy_price"]) * sell_amount,
                    "amount": sell_amount,
                    "timestamp": datetime.now(),
                    "reason": reason
                })
                
                category = trade_bot.token_categories.get(mint_address, "unknown")
                trade_bot.positions_by_category[category] -= 1
                del trade_bot.positions[mint_address]
                
                trade_bot.update_log(
                    mint_address,
                    f"✅ {reason}: {mint_address} - {sell_amount} SOL satıldı, "
                    f"Fiyat: ${format_price(current_price)}, TX: {tx_hash}"
                )
                
                if mint_address in trade_bot.trade_start_times:
                    del trade_bot.trade_start_times[mint_address]
                    
                if mint_address in trade_bot.trade_windows:
                    trade_bot.update_log(
                        mint_address,
                        f"ℹ️ Pencere 10 saniye sonra otomatik kapanacak..."
                    )
                    trade_bot.root.after(10000, lambda: close_trade_window(trade_bot, mint_address))
            
            # E-posta bildirimi
            try:
                from gotnw_tradebot.utils.network_utils import send_email
                
                profit_loss = (current_price - data["buy_price"]) * sell_amount
                profit_loss_pct = ((current_price - data["buy_price"]) / data["buy_price"]) * 100
                
                send_email(
                    f"Satış Başarılı - {reason}",
                    f"Token: {(await get_token_info(trade_bot, mint_address))['symbol']} ({mint_address})\n"
                    f"Miktar: {sell_amount} SOL\n"
                    f"Fiyat: ${format_price(current_price)}\n"
                    f"Kâr/Zarar: ${format_price(profit_loss)} (%{profit_loss_pct:.2f})\n"
                    f"TX: {tx_hash}\n"
                    f"Neden: {reason}"
                )
            except Exception as e:
                trade_bot.update_log(mint_address, f"E-posta gönderme hatası: {e}")
            
            # Durumu kaydet
            if trade_bot.save_state:
                await trade_bot.save_state()
                
            return True, tx_hash
            
        else:
            trade_bot.update_log(mint_address, f"❌ {reason} işlemi başarısız oldu")
            return False, None
            
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"SATIM HATASI: {mint_address}\n{error_details}")
        log_to_file(f"Satım hatası: {mint_address}\n{error_details}")
        
        trade_bot.update_log(mint_address, f"❌ Satım işlemi hatası: {e}")
        return False, None
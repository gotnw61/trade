# -*- coding: utf-8 -*-
"""
Pozisyon yönetimi modülü
"""

from datetime import datetime
from loguru import logger

from gotnw_tradebot.utils.logging_utils import log_to_file
from gotnw_tradebot.utils.formatting import format_price
from gotnw_tradebot.utils.network_utils import send_email
from gotnw_tradebot.core.price_manager import get_token_info
from gotnw_tradebot.core.trade_window import close_trade_window


def calculate_profit_percentage(trade_bot, mint_address):
    """
    Belirli bir pozisyonun kâr/zarar yüzdesini hesaplar
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address (str): Token mint adresi
        
    Returns:
        float: Kâr/zarar yüzdesi
    """
    if mint_address not in trade_bot.positions:
        return 0
        
    data = trade_bot.positions[mint_address]
    current_price = trade_bot.websocket_prices.get(mint_address) or data.get("buy_price", 0)
    buy_price = data.get("buy_price", 0)
    
    if buy_price <= 0:
        return 0
        
    return ((current_price - buy_price) / buy_price) * 100


async def take_partial_profit(trade_bot, mint_address, percentage, reason):
    """
    Bir pozisyonun belirli bir yüzdesini kâr alarak kapatır
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address (str): Token mint adresi
        percentage (float): Satılacak yüzde
        reason (str): Satış nedeni
        
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
    
    from gotnw_tradebot.core.price_manager import get_token_price
    current_price = await get_token_price(trade_bot, mint_address, force_update=True)
    if not current_price:
        trade_bot.update_log(mint_address, "❌ Fiyat alınamadı, işlem iptal edildi")
        return False
        
    # Swap işlemini gerçekleştir
    from gotnw_tradebot.core.trade_executor import execute_swap
    tx_hash = await execute_swap(trade_bot, mint_address, sell_amount, buy=False)
    
    if tx_hash:
        # Pozisyonu güncelle
        data["remaining_amount"] -= sell_amount
        data["remaining_token_amount"] -= data["remaining_token_amount"] * (percentage / 100)
        
        trade_bot.update_log(
            mint_address,
            f"✅ {reason} nedeniyle kısmi kâr alma: {mint_address} - {percentage}% ({sell_amount} SOL) @ ${format_price(current_price)}"
        )
        
        # Geçmiş işlemlere ekle
        trade_bot.past_trades.append({
            "mint": mint_address,
            "symbol": (await get_token_info(trade_bot, mint_address))["symbol"],
            "buy_price": data["buy_price"],
            "sell_price": current_price,
            "profit_loss": (current_price - data["buy_price"]) * sell_amount,
            "amount": sell_amount,
            "timestamp": datetime.now(),
            "reason": f"Kısmi Kâr Alma - {reason}"
        })
        
        # Eğer pozisyon tamamen kapandıysa
        if data["remaining_amount"] <= 0:
            category = trade_bot.token_categories.get(mint_address, "unknown")
            trade_bot.positions_by_category[category] -= 1
            del trade_bot.positions[mint_address]
            
            if mint_address in trade_bot.trade_start_times:
                del trade_bot.trade_start_times[mint_address]
                
            if mint_address in trade_bot.trade_windows:
                trade_bot.update_log(
                    mint_address,
                    f"ℹ️ Pencere 10 saniye sonra otomatik kapanacak..."
                )
                trade_bot.root.after(10000, lambda: close_trade_window(trade_bot, mint_address))
                
            trade_bot.update_log(
                mint_address,
                f"ℹ️ Pozisyon kapandı. Kapanma sebebi: Kısmi Kâr Alma - {reason}"
            )
            
        # E-posta bildirimi
        try:
            profit_loss = (current_price - data["buy_price"]) * sell_amount
            profit_loss_pct = ((current_price - data["buy_price"]) / data["buy_price"]) * 100
            
            send_email(
                f"Kısmi Kâr Alma - {reason}",
                f"Token: {(await get_token_info(trade_bot, mint_address))['symbol']} ({mint_address})\n"
                f"Miktar: {sell_amount} SOL (%{percentage})\n"
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
            
        return True
    
    else:
        trade_bot.update_log(mint_address, f"❌ Kâr alma işlemi başarısız oldu: {reason}")
        return False


def update_position(trade_bot, mint_address, current_price, amount, token_amount, tp_levels):
    """
    Yeni bir pozisyon oluşturur veya mevcut pozisyonu günceller
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address (str): Token mint adresi
        current_price (float): Güncel fiyat
        amount (float): Alım miktarı (SOL)
        token_amount (float): Token miktarı
        tp_levels (list): TP seviyeleri
    """
    # Pozisyonu oluştur/güncelle
    trade_bot.positions[mint_address] = {
        "buy_price": current_price,
        "amount": amount,
        "remaining_amount": amount,
        "token_amount": token_amount,
        "remaining_token_amount": token_amount,
        "tp_levels": tp_levels,
        "sl_levels": trade_bot.config.trade_settings["sell_stop_loss_levels"].copy(),
        "highest_price": current_price
    }
    
    # İşlenen mintlere ekle
    trade_bot.processed_mints.add(mint_address)
    
    # Kategori takibi için
    category = trade_bot.token_categories.get(mint_address, "unknown")
    trade_bot.positions_by_category[category] += 1
    
    logger.info(f"Pozisyon oluşturuldu/güncellendi: {mint_address}, {amount} SOL @ ${format_price(current_price)}")


async def close_position(trade_bot, mint_address, reason="Manuel Kapatma"):
    """
    Belirli bir pozisyonu kapatır
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address (str): Token mint adresi
        reason (str): Kapatma nedeni
        
    Returns:
        bool: İşlem başarısı
    """
    if mint_address not in trade_bot.positions:
        return False
    
    try:
        data = trade_bot.positions[mint_address]
        remaining_amount = data["remaining_amount"]
        
        if remaining_amount <= 0:
            trade_bot.update_log(mint_address, "❌ Kalan miktar sıfır, pozisyon zaten kapalı")
            return False
        
        # Güncel fiyatı al
        from gotnw_tradebot.core.price_manager import get_token_price
        current_price = await get_token_price(trade_bot, mint_address, force_update=True)
        
        if not current_price:
            trade_bot.update_log(mint_address, "❌ Fiyat alınamadı, işlem iptal edildi")
            return False
        
        # Swap işlemini gerçekleştir
        from gotnw_tradebot.core.trade_executor import execute_swap
        tx_hash = await execute_swap(trade_bot, mint_address, remaining_amount, buy=False)
        
        if tx_hash:
            # Geçmiş işlemlere ekle
            trade_bot.past_trades.append({
                "mint": mint_address,
                "symbol": (await get_token_info(trade_bot, mint_address))["symbol"],
                "buy_price": data["buy_price"],
                "sell_price": current_price,
                "profit_loss": (current_price - data["buy_price"]) * remaining_amount,
                "amount": remaining_amount,
                "timestamp": datetime.now(),
                "reason": reason
            })
            
            # Pozisyonu kaldır
            category = trade_bot.token_categories.get(mint_address, "unknown")
            trade_bot.positions_by_category[category] -= 1
            del trade_bot.positions[mint_address]
            
            # Bağlantılı verileri temizle
            if mint_address in trade_bot.trade_start_times:
                del trade_bot.trade_start_times[mint_address]
                
            # İşlem penceresini kapat
            if mint_address in trade_bot.trade_windows:
                trade_bot.update_log(
                    mint_address,
                    f"ℹ️ Pencere 10 saniye sonra otomatik kapanacak..."
                )
                trade_bot.root.after(10000, lambda: close_trade_window(trade_bot, mint_address))
            
            # Log
            trade_bot.update_log(
                mint_address,
                f"✅ Pozisyon kapatıldı: {mint_address}, {remaining_amount} SOL @ ${format_price(current_price)}, Neden: {reason}"
            )
            
            # E-posta bildirimi
            try:
                profit_loss = (current_price - data["buy_price"]) * remaining_amount
                profit_loss_pct = ((current_price - data["buy_price"]) / data["buy_price"]) * 100
                
                send_email(
                    f"Pozisyon Kapatma - {reason}",
                    f"Token: {(await get_token_info(trade_bot, mint_address))['symbol']} ({mint_address})\n"
                    f"Miktar: {remaining_amount} SOL\n"
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
                
            return True
        
        else:
            trade_bot.update_log(mint_address, f"❌ Pozisyon kapatma işlemi başarısız oldu")
            return False
            
    except Exception as e:
        log_to_file(f"Pozisyon kapatma hatası: {mint_address}, {e}")
        logger.error(f"Pozisyon kapatma hatası: {mint_address}, {e}")
        return False


async def get_position_info(trade_bot, mint_address):
    """
    Pozisyon bilgilerini getirir
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address (str): Token mint adresi
        
    Returns:
        dict: Pozisyon bilgileri veya None (pozisyon yoksa)
    """
    if mint_address not in trade_bot.positions:
        return None
    
    data = trade_bot.positions[mint_address]
    
    # Güncel fiyatı al
    from gotnw_tradebot.core.price_manager import get_token_price
    current_price = await get_token_price(trade_bot, mint_address, force_update=False)
    
    if not current_price:
        current_price = data.get("buy_price", 0)
    
    # Token bilgilerini al
    token_info = await get_token_info(trade_bot, mint_address)
    
    # Başlangıç zamanı
    start_time = trade_bot.trade_start_times.get(mint_address, datetime.now())
    elapsed = datetime.now() - start_time
    
    # Kâr/zarar hesaplama
    buy_price = data.get("buy_price", 0)
    profit_loss_pct = ((current_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0
    profit_loss_abs = (current_price - buy_price) * data.get("remaining_token_amount", 0)
    
    return {
        "mint_address": mint_address,
        "symbol": token_info.get("symbol", "Bilinmeyen") if token_info else "Bilinmeyen",
        "buy_price": buy_price,
        "current_price": current_price,
        "highest_price": data.get("highest_price", buy_price),
        "amount": data.get("amount", 0),
        "remaining_amount": data.get("remaining_amount", 0),
        "token_amount": data.get("token_amount", 0),
        "remaining_token_amount": data.get("remaining_token_amount", 0),
        "start_time": start_time,
        "elapsed_seconds": elapsed.total_seconds(),
        "elapsed_str": f"{elapsed.seconds // 60}m {elapsed.seconds % 60}s",
        "profit_loss_percentage": profit_loss_pct,
        "profit_loss_absolute": profit_loss_abs,
        "tp_levels": data.get("tp_levels", []),
        "sl_levels": data.get("sl_levels", []),
        "category": trade_bot.token_categories.get(mint_address, "unknown"),
        "liquidity": token_info.get("liquidity_usd", 0) if token_info else 0,
        "volume": token_info.get("volume", 0) if token_info else 0
    }


async def get_all_positions(trade_bot):
    """
    Tüm aktif pozisyonların bilgilerini getirir
    
    Args:
        trade_bot: TradeBot nesnesi
        
    Returns:
        list: Pozisyon bilgileri listesi
    """
    positions = []
    
    for mint_address in list(trade_bot.positions.keys()):
        position_info = await get_position_info(trade_bot, mint_address)
        if position_info:
            positions.append(position_info)
    
    return positions


async def get_portfolio_summary(trade_bot):
    """
    Portföy özeti oluşturur
    
    Args:
        trade_bot: TradeBot nesnesi
        
    Returns:
        dict: Portföy özeti
    """
    positions = await get_all_positions(trade_bot)
    
    total_investment = sum(pos["amount"] for pos in positions)
    current_value = sum(pos["remaining_amount"] for pos in positions)
    total_profit_loss = sum(pos["profit_loss_absolute"] for pos in positions)
    
    # Kategorilere göre pozisyonlar
    positions_by_category = {}
    for pos in positions:
        category = pos["category"]
        if category not in positions_by_category:
            positions_by_category[category] = []
        positions_by_category[category].append(pos)
    
    # Kârlı pozisyon sayısı
    profitable_positions = sum(1 for pos in positions if pos["profit_loss_percentage"] > 0)
    
    # En kârlı ve en zararlı pozisyonlar
    most_profitable = max(positions, key=lambda p: p["profit_loss_percentage"]) if positions else None
    most_unprofitable = min(positions, key=lambda p: p["profit_loss_percentage"]) if positions else None
    
    return {
        "total_positions": len(positions),
        "total_investment": total_investment,
        "current_value": current_value,
        "total_profit_loss": total_profit_loss,
        "total_profit_loss_percentage": (total_profit_loss / total_investment * 100) if total_investment > 0 else 0,
        "profitable_positions": profitable_positions,
        "positions_by_category": positions_by_category,
        "most_profitable": most_profitable,
        "most_unprofitable": most_unprofitable
    }
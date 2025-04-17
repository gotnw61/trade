# -*- coding: utf-8 -*-
"""
Alım işlemleri mantığı modülü
"""

import asyncio
import random
import string
import time
import traceback
from datetime import datetime

from loguru import logger

from config import trade_settings
from utils.console_utils import animated_text
from utils.logging_utils import log_to_file
from utils.trade_utils import check_trading_hours
from wallet.wallet_manager import get_available_balance
from core.trade_executor import execute_swap
from core.price_manager import get_token_price, get_token_info


async def validate_token_for_buy(trade_bot, mint_address):
    """
    Token'ın alım için uygun olup olmadığını kontrol eder.
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address: Token mint adresi
    
    Returns:
        bool: Token alım için uygunsa True, değilse False
    """
    if mint_address == "So11111111111111111111111111111111111111112":
        trade_bot.update_log(mint_address, "❌ SOL tokeni tekrar alınamaz")
        return False

    if mint_address in trade_bot.positions:
        trade_bot.update_log(mint_address, f"⚠️ Bu token için zaten bir pozisyon var: {mint_address}")
        return False

    if trade_bot.check_token_exists_in_any_positions(mint_address):
        trade_bot.update_log(mint_address, f"⚠️ Bu token daha önce işlenmiş ve pozisyon alınmış: {mint_address}")
        return False
        
    return True


async def validate_balance(trade_bot, amount, balance):
    """
    Bakiyenin alım için yeterli olup olmadığını kontrol eder.
    
    Args:
        trade_bot: TradeBot nesnesi
        amount: Alım miktarı
        balance: Mevcut bakiye
    
    Returns:
        bool: Bakiye yeterliyse True, değilse False
    """
    if not isinstance(balance, (int, float)) or balance < amount + trade_settings["min_balance_sol"]:
        animated_text(
            f"❌ Yetersiz bakiye: {balance} SOL (Gerekli: {amount + trade_settings['min_balance_sol']} SOL)"
        )
        return False
    return True


async def prepare_buy_transaction(trade_bot, mint_address, amount):
    """
    Alım işlemi için gerekli hazırlıkları yapar.
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address: Token mint adresi
        amount: Alım miktarı
    
    Returns:
        dict or None: Token bilgileri ve alım parametreleri, başarısız olursa None
    """
    token_info = None
    start_time = time.time()
    retry_count = 0
    max_retries = 5

    while time.time() - start_time < 60 and retry_count < max_retries:
        try:
            token_info = await get_token_info(trade_bot, mint_address, force_update=True)
            if token_info is not None:
                break
            trade_bot.update_log(mint_address, f"ℹ️ Token bilgisi alınamadı, tekrar deneniyor ({retry_count+1}/{max_retries})")
            retry_count += 1
            await asyncio.sleep(1)
        except Exception as e:
            trade_bot.update_log(mint_address, f"Token bilgisi alma hatası: {e}")
            retry_count += 1
            await asyncio.sleep(1)

    if token_info is None:
        message = f"❌ Token bilgisi {max_retries} denemede alınamadı: {mint_address}"
        trade_bot.update_log(mint_address, message)
        return None

    current_price = token_info.get("price_usd", 0)
    if not current_price or current_price <= 0:
        message = f"❌ Geçersiz token fiyatı: {current_price} için {mint_address}"
        trade_bot.update_log(mint_address, message)
        return None

    trade_bot.update_log(mint_address, f"ℹ️ Güncel fiyat: ${trade_bot.format_price(current_price)}")

    if current_price < 0.000007000:
        message = f"❌ Fiyat çok düşük: ${trade_bot.format_price(current_price)} < $0.000007000 için {mint_address}"
        trade_bot.update_log(mint_address, message)
        return None

    # Token kategorisini belirle
    category = trade_bot.analyzer.categorize_token(token_info)
    trade_bot.token_categories[mint_address] = category
    trade_bot.update_log(mint_address, f"ℹ️ Token kategorisi: {category}")

    # SOL fiyatını al
    from utils.network_utils import get_sol_price
    sol_price = await get_sol_price()
    if sol_price is None or sol_price <= 0 or sol_price > 1000:
        sol_price = 150.0
        trade_bot.update_log(mint_address, f"ℹ️ SOL fiyatı alınamadı, varsayılan: ${sol_price}")

    return {
        "token_info": token_info,
        "current_price": current_price,
        "category": category,
        "sol_price": sol_price
    }


async def check_buy_confirmation(trade_bot, mint_address, manual):
    """
    Alım için onay kontrolleri yapar.
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address: Token mint adresi
        manual: Manuel alım mı?
    
    Returns:
        dict or None: Onay sonuçları, başarısız olursa None
    """
    confirmation_result = trade_bot.analyzer.get_multi_confirmation_signal(mint_address)
    if not confirmation_result["is_confirmed"] and not manual:
        trade_bot.update_log(
            mint_address,
            f"⚠️ Çoklu gösterge onayı alınamadı: {confirmation_result['confirmations']}/{confirmation_result['total_indicators']} (%{confirmation_result['confidence']:.0f} güven)"
        )
        return None

    time_check = check_trading_hours()
    buy_amount_multiplier = 1.0
    
    if time_check["risk_level"] == "high" and not manual:
        buy_amount_multiplier = 0.5
        trade_bot.update_log(
            mint_address,
            f"ℹ️ Yüksek volatilite saatlerinde işlem: {time_check['reason']} - Pozisyon boyutu %50 azaltıldı"
        )
    
    return {
        "confirmation_result": confirmation_result,
        "time_check": time_check,
        "buy_amount_multiplier": buy_amount_multiplier
    }


async def process_buy_transaction(trade_bot, mint_address, amount=None, detection_time=None, manual=False,
                                 pump_detected=False, momentum_detected=False, dip_detected=False, ai_detected=False):
    """
    Alım işlemini gerçekleştirir.
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address: Token mint adresi
        amount: Alım miktarı (varsayılan None)
        detection_time: Tespit zamanı
        manual: Manuel alım mı?
        pump_detected: Pump tespit edildi mi?
        momentum_detected: Momentum tespit edildi mi?
        dip_detected: Dip tespit edildi mi?
        ai_detected: AI tarafından tespit edildi mi?
    
    Returns:
        bool: İşlem başarılıysa True, değilse False
    """
    try:
        # Alım miktarı belirleme
        if amount is None:
            amount = trade_settings["buy_amount_sol"]

        # Token uygunluğunu kontrol et
        if not await validate_token_for_buy(trade_bot, mint_address):
            return False

        # Bakiye kontrolü
        balance = await get_available_balance()
        if not await validate_balance(trade_bot, amount, balance):
            return False

        # Alım işlemi için hazırlık
        buy_params = await prepare_buy_transaction(trade_bot, mint_address, amount)
        if buy_params is None:
            return False

        token_info = buy_params["token_info"]
        current_price = buy_params["current_price"]
        category = buy_params["category"]
        sol_price = buy_params["sol_price"]

        # Onay kontrolleri
        confirmation = await check_buy_confirmation(trade_bot, mint_address, manual)
        if confirmation is None:
            return False

        buy_amount_multiplier = confirmation["buy_amount_multiplier"]
        adjusted_amount = amount * buy_amount_multiplier

        # Swap işlemi gerçekleştir
        trade_result = await execute_swap(
            trade_bot,
            mint_address=mint_address,
            amount=adjusted_amount,
            trade_type="buy",
            token_info=token_info
        )

        if not trade_result["success"]:
            trade_bot.update_log(mint_address, f"❌ Alım işlemi başarısız: {trade_result['message']}")
            return False

        # Pozisyon güncelleme
        from core.position_manager import update_position
        await update_position(
            trade_bot,
            mint_address=mint_address,
            amount=adjusted_amount,
            price=current_price,
            trade_type="buy",
            token_info=token_info
        )

        # İşlem kaydı
        trade_bot.daily_trades.append({
            "type": "buy",
            "mint": mint_address,
            "amount": adjusted_amount,
            "price": current_price,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        trade_bot.update_log(
            mint_address,
            f"✅ Alım başarılı: {adjusted_amount:.4f} SOL @ ${trade_bot.format_price(current_price)} "
            f"(Kategori: {category})"
        )
        return True

    except Exception as e:
        trade_bot.update_log(mint_address, f"❌ Alım işleminde hata: {str(e)}")
        logger.error(f"Alım hatası: {traceback.format_exc()}")
        return False
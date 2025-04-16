# -*- coding: utf-8 -*-
"""
Alım/satım analizi modülü - token dinamiklerini inceleyerek alım/satım sinyalleri üretir
"""

import traceback
from loguru import logger

from gotnw_tradebot.config import trade_settings, DEBUG_MODE
from gotnw_tradebot.utils.logging_utils import log_to_file


async def analyze_token_dynamics(trade_bot, mint_address, current_price, token_info, price_change_pct):
    """
    Token dinamiklerini analiz eder ve alım/satım sinyalleri üretir
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address (str): Token mint adresi
        current_price (float or dict): Güncel fiyat veya fiyat içeren nesne
        token_info (dict): Token bilgileri
        price_change_pct (float): Fiyat değişim yüzdesi
        
    Returns:
        dict or None: Analiz sonuçları veya None (başarısız ise)
    """
    if DEBUG_MODE:
        trade_bot.update_log(mint_address, f"DEBUG: current_price tipi: {type(current_price)}, değeri: {current_price}")
        trade_bot.update_log(mint_address, f"DEBUG: token_info tipi: {type(token_info)}, değeri: {token_info}")
    try:
        # Geçerli fiyat oluştur
        if not isinstance(current_price, (int, float)):
            if isinstance(current_price, dict) and "price_usd" in current_price:
                current_price = current_price["price_usd"]
            else:
                current_price = float(current_price) if hasattr(current_price, "__float__") else 0
                trade_bot.update_log(mint_address, f"⚠️ Geçersiz fiyat tipi dönüştürüldü: {type(current_price)}")
        
        # Geçerli token_info oluştur
        if not isinstance(token_info, dict):
            token_info = {} if token_info is None else {"price_usd": current_price}
            trade_bot.update_log(mint_address, f"⚠️ Geçersiz token_info tipi dönüştürüldü: {type(token_info)}")
            
        # Pozisyon durumunu kontrol et
        in_position = mint_address in trade_bot.positions
        
        # Analiz metriklerini hesapla
        momentum = trade_bot.analyzer.calculate_momentum(mint_address)
        volatility = trade_bot.analyzer.calculate_volatility(mint_address)
        
        # Likidite metrikleri
        liquidity_usd = token_info.get("liquidity_usd", 0)
        if not isinstance(liquidity_usd, (int, float)):
            liquidity_usd = 0
            
        liquidity_change = trade_bot.analyzer.detect_liquidity_change(mint_address, liquidity_usd)
        
        # Fiyat sapma metriği
        price_deviation = trade_bot.analyzer.detect_price_deviation(mint_address, current_price)
        
        # Dip tespiti
        dip_result = trade_bot.analyzer.detect_dip(mint_address, current_price)
        dip_percentage = dip_result["metrics"]["dip_percentage"] if isinstance(dip_result, dict) and "metrics" in dip_result else 0
        
        # Hacim metriği
        volume = token_info.get("volume", 0)
        if not isinstance(volume, (int, float)):
            volume = 0
            
        volume_drop = trade_bot.analyzer.detect_volume_drop(mint_address, volume)
        
        # Tüm metrikleri topla
        dynamics = {
            "in_position": in_position,
            "momentum": momentum,
            "volatility": volatility,
            "liquidity_change": liquidity_change,
            "price_deviation": price_deviation,
            "dip_percentage": dip_percentage,
            "volume_drop": volume_drop
        }
        
        # Alım/satım sinyalleri üret
        # Sadece önemli fiyat değişimlerini kaydet
        if abs(price_change_pct) > 2:
            tx_type = "buy" if price_change_pct > 0 else "sell"
            estimated_amount = abs(price_change_pct) * 0.01
            trade_bot.analyzer.record_transaction(
                mint_address, estimated_amount, tx_type, price=current_price
            )
        
        # AI tabanlı pump tahmini
        is_pump, pump_probability = trade_bot.analyzer.predict_pump_with_ai(
            mint_address, current_price, token_info.get("volume", 0), momentum, volatility
        )
        
        # Balina dump tespiti
        whale_dump, whale_dump_amount = trade_bot.analyzer.detect_whale_dump(mint_address)
        
        # Alım sinyalleri üret (pozisyonda değilken)
        if not in_position and trade_settings["autobuy_enabled"] and mint_address not in trade_bot.pending_buys:
            await _check_buy_signals(
                trade_bot, mint_address, current_price, momentum, dip_percentage, 
                is_pump, pump_probability
            )
        # Satım sinyalleri üret (pozisyondayken)
        elif in_position:
            await _check_sell_signals(
                trade_bot, mint_address, current_price, whale_dump, whale_dump_amount,
                liquidity_change, volatility
            )
        
        # Hacim düşüşü kontrolü
        if (trade_settings["volume_drop_detection_enabled"] and
                volume_drop >= trade_settings["volume_drop_threshold"]):
            trade_bot.update_log(
                mint_address,
                f"Hacim Düşüş Uyarısı: {mint_address} - Düşüş: {volume_drop:.2f}%"
            )
            if in_position and calculate_profit_percentage(trade_bot, mint_address) > 0:
                from gotnw_tradebot.core.position_manager import take_partial_profit
                await take_partial_profit(trade_bot, mint_address, 25, "Hacim Düşüşü")
        
        return dynamics
    
    except Exception as e:
        error_traceback = traceback.format_exc()
        trade_bot.update_log(mint_address, f"Token dinamiği analiz hatası: {e}")
        trade_bot.update_log(mint_address, f"Hata traceback: {error_traceback}")
        log_to_file(f"Token dinamiği analiz hatası: {mint_address}, {e}\n{error_traceback}")
        return None


async def _check_buy_signals(trade_bot, mint_address, current_price, momentum, dip_percentage,
                             is_pump, pump_probability):
    """
    Alım sinyallerini kontrol eder
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address (str): Token mint adresi
        current_price (float): Güncel fiyat
        momentum (float): Momentum değeri
        dip_percentage (float): Dip yüzdesi
        is_pump (bool): Pump tespit edildi mi
        pump_probability (float): Pump olasılığı
    """
    # Çeşitlendirme kontrolü
    diversification_ok = check_token_diversification(trade_bot, mint_address)
    if not diversification_ok:
        return
    
    # Momentum kontrolü
    if (trade_settings["momentum_enabled"] and
            momentum >= trade_settings["momentum_threshold"]):
        trade_bot.update_log(
            mint_address,
            f"Momentum Alım Sinyali: {mint_address} - Momentum: {momentum:.2f}%"
        )
        trade_bot.pending_buys.add(mint_address)
        from gotnw_tradebot.core.buy_logic import process_buy_transaction
        asyncio.create_task(
            process_buy_transaction(
                trade_bot, mint_address,
                detection_time=datetime.now(),
                manual=False,
                momentum_detected=True
            )
        )
    # Dip kontrolü
    elif (trade_settings["dip_buy_enabled"] and
          dip_percentage >= trade_settings["dip_buy_threshold"]):
        trade_bot.update_log(
            mint_address,
            f"Dip Alım Sinyali: {mint_address} - Düşüş: {dip_percentage:.2f}%"
        )
        trade_bot.pending_buys.add(mint_address)
        from gotnw_tradebot.core.buy_logic import process_buy_transaction
        asyncio.create_task(
            process_buy_transaction(
                trade_bot, mint_address,
                detection_time=datetime.now(),
                manual=False,
                dip_detected=True
            )
        )
    # AI kontrolü
    elif (trade_settings["ai_enabled"] and is_pump and
          pump_probability >= trade_settings["ai_confidence_threshold"]):
        trade_bot.update_log(
            mint_address,
            f"AI Pump Tahmini: {mint_address} - Olasılık: {pump_probability:.2f}"
        )
        trade_bot.pending_buys.add(mint_address)
        from gotnw_tradebot.core.buy_logic import process_buy_transaction
        asyncio.create_task(
            process_buy_transaction(
                trade_bot, mint_address,
                detection_time=datetime.now(),
                manual=False,
                ai_detected=True
            )
        )


async def _check_sell_signals(trade_bot, mint_address, current_price, whale_dump, whale_dump_amount,
                               liquidity_change, volatility):
    """
    Satım sinyallerini kontrol eder
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address (str): Token mint adresi
        current_price (float): Güncel fiyat
        whale_dump (bool): Balina dump tespit edildi mi
        whale_dump_amount (float): Balina dump miktarı
        liquidity_change (float): Likidite değişim yüzdesi
        volatility (float): Volatilite değeri
    """
    from gotnw_tradebot.core.position_manager import calculate_profit_percentage, take_partial_profit
    from gotnw_tradebot.core.sell_logic import emergency_sell
    
    # Balina dump tespiti
    if (trade_settings["whale_dump_detection_enabled"] and whale_dump):
        trade_bot.update_log(
            mint_address,
            f"Balina Dump Tespiti: {mint_address} - Miktar: {whale_dump_amount} SOL"
        )
        await emergency_sell(trade_bot, mint_address, "Balina Dump Tespiti")
    
    # Likidite çıkış kontrolü
    elif (trade_settings["liquidity_exit_enabled"] and
          liquidity_change <= -trade_settings["liquidity_exit_threshold"]):
        trade_bot.update_log(
            mint_address,
            f"Likidite Çıkış Sinyali: {mint_address} - Değişim: {liquidity_change:.2f}%"
        )
        await emergency_sell(trade_bot, mint_address, "Likidite Azalması")
    
    # Volatilite kontrolü
    elif (trade_settings["volatility_trading_enabled"] and
          volatility >= trade_settings["volatility_threshold"]):
        profit_percentage = calculate_profit_percentage(trade_bot, mint_address)
        if profit_percentage > 5:
            trade_bot.update_log(
                mint_address,
                f"Volatilite Kâr Alma: {mint_address} - Volatilite: {volatility:.2f}%"
            )
            await take_partial_profit(trade_bot, mint_address, 50, "Yüksek Volatilite")
    
    # AI fiyat tahmini
    if trade_settings["ai_enabled"] and hasattr(trade_bot.analyzer, 'predict_future_price'):
        future_price = trade_bot.analyzer.predict_future_price(mint_address)
        if future_price is not None and future_price < current_price:
            price_drop_pct = ((current_price - future_price) / current_price) * 100
            profit_percentage = calculate_profit_percentage(trade_bot, mint_address)
            if price_drop_pct > 5 and profit_percentage > 10:
                trade_bot.update_log(
                    mint_address,
                    f"AI Fiyat Düşüş Tahmini: {mint_address} - %{price_drop_pct:.2f} düşüş bekleniyor"
                )
                await take_partial_profit(trade_bot, mint_address, 50, "AI Fiyat Düşüş Tahmini")


def check_token_diversification(trade_bot, mint_address):
    """
    Token çeşitlendirme kontrolü yapar
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address (str): Token mint adresi
        
    Returns:
        bool: Çeşitlendirme kriterlerine uygunsa True, değilse False
    """
    if not trade_settings["token_diversification_enabled"]:
        return True
        
    category = trade_bot.token_categories.get(mint_address, "unknown")
    
    # Kategori bazında pozisyon limiti kontrolü
    if trade_bot.positions_by_category[category] >= trade_settings["max_positions_per_category"]:
        trade_bot.update_log(
            mint_address,
            f"Çeşitlendirme limiti aşıldı: {category} kategorisinde maksimum pozisyon sayısına ulaşıldı"
        )
        return False
    
    # Toplam pozisyon limiti kontrolü
    if len(trade_bot.positions) >= trade_settings["max_positions"]:
        trade_bot.update_log(
            mint_address,
            f"Maksimum pozisyon sayısına ulaşıldı: {len(trade_bot.positions)}/{trade_settings['max_positions']}"
        )
        return False
    
    return True


def calculate_profit_percentage(trade_bot, mint_address):
    """
    Pozisyonun kâr/zarar yüzdesini hesaplar
    
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
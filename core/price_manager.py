# -*- coding: utf-8 -*-
"""
Fiyat yönetimi modülü - token fiyatları ve bilgilerini almak için fonksiyonlar
"""

import time
import threading
import requests
import aiohttp
import asyncio
from loguru import logger

from gotnw_tradebot.utils.logging_utils import log_to_file
from gotnw_tradebot.utils.formatting import format_price
from gotnw_tradebot.utils.network_utils import get_sol_price


# Token bilgisi cache'i (performans için)
_token_cache = {}
_cache_time = {}


async def get_token_info(trade_bot, mint_address, force_update=False):
    """
    Belirli bir token için bilgileri getirir
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address (str): Token mint adresi
        force_update (bool): Her zaman güncel veri almak için
        
    Returns:
        dict: Token bilgileri veya None (başarısız ise)
    """
    now = time.time()
    if not force_update and mint_address in trade_bot.price_cache and now - trade_bot.last_price_update.get(mint_address, 0) < 30:
        return trade_bot.price_cache[mint_address]
    
    if trade_bot.websocket_prices.get(mint_address) and not force_update:
        return {
            "symbol": "Bilinmeyen",
            "price_usd": trade_bot.websocket_prices[mint_address],
            "liquidity_usd": 10000,
            "market_cap": 0,
            "volume": 0
        }
    
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://api.dexscreener.com/latest/dex/tokens/{mint_address}",
                    timeout=2
                ) as response:
                    if response.status != 200:
                        continue
                    
                    data = await response.json()
                    
                    if data.get("pairs"):
                        pair = data["pairs"][0]
                        liquidity = pair.get("liquidity", {})
                        price_usd = float(pair.get("priceUsd", 0))
                        
                        if price_usd < 0.0000001 or price_usd > 10000:
                            continue
                            
                        info = {
                            "symbol": pair.get("baseToken", {}).get("symbol", "Bilinmeyen"),
                            "price_usd": price_usd,
                            "liquidity_usd": float(liquidity.get("usd", 0)),
                            "market_cap": float(pair.get("marketCap", 0)),
                            "volume": float(pair.get("volume", {}).get("h24", 0))
                        }
                        
                        # Cache güncelleme
                        trade_bot.price_cache[mint_address] = info
                        trade_bot.last_price_update[mint_address] = now
                        
                        # Fiyat geçmişine ekle
                        from datetime import datetime
                        trade_bot.price_history[mint_address].append(
                            {"timestamp": datetime.now(), "price_usd": price_usd}
                        )
                        
                        # Analiz için fiyat geçmişini güncelle
                        trade_bot.analyzer.update_price_history(mint_address, price_usd)
                        trade_bot.analyzer.update_volume_history(mint_address, info.get("volume", 0))
                        trade_bot.analyzer.update_liquidity_history(mint_address, info.get("liquidity_usd", 0))
                        
                        return info
        
        except aiohttp.ClientError as e:
            if attempt < 2:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Token bilgisi alma hatası: {e}")
    
    # DexScreener başarısız olduysa, Jupiter'i dene
    try:
        quote_url = "https://quote-api.jup.ag/v6/quote"
        params = {
            "inputMint": "So11111111111111111111111111111111111111112",
            "outputMint": mint_address,
            "amount": 1000000000,
            "slippageBps": 100
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(quote_url, params=params, timeout=2) as response:
                if response.status != 200:
                    return None
                
                quote_data = await response.json()
                
                # SOL fiyatını al
                sol_price = await get_sol_price()
                if sol_price is None or sol_price <= 0:
                    sol_price = 150.0  # Varsayılan
                
                # Fiyat hesaplama
                out_amount = float(quote_data.get("outAmount", 0))
                jupiter_price = (out_amount / 1_000_000_000) * sol_price
                
                if jupiter_price < 0.0000001 or jupiter_price > 10000:
                    return None
                    
                info = {
                    "symbol": "Bilinmeyen",
                    "price_usd": jupiter_price,
                    "liquidity_usd": 0,
                    "market_cap": 0,
                    "volume": 0
                }
                
                # Cache güncelleme
                trade_bot.price_cache[mint_address] = info
                trade_bot.last_price_update[mint_address] = now
                
                # Fiyat geçmişine ekle
                from datetime import datetime
                trade_bot.price_history[mint_address].append(
                    {"timestamp": datetime.now(), "price_usd": jupiter_price}
                )
                
                return info
    
    except Exception as e:
        logger.error(f"Jupiter API fiyat alma hatası: {e}")
        return None


async def get_token_price(trade_bot, mint_address, force_update=False):
    """
    Belirli bir token için fiyat bilgisini getirir
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address (str): Token mint adresi
        force_update (bool): Her zaman güncel veri almak için
        
    Returns:
        float: Token fiyatı veya None (başarısız ise)
    """
    attempts = 0
    max_attempts = 5
    
    while attempts < max_attempts:
        try:
            # WebSocket fiyatı var mı kontrol et
            if not force_update and mint_address in trade_bot.websocket_prices:
                price = trade_bot.websocket_prices[mint_address]
                if 0.0000001 < price < 10000:
                    return price
            
            # Cache'den fiyat kontrolü
            if not force_update and mint_address in trade_bot.price_cache:
                now = time.time()
                if now - trade_bot.last_price_update.get(mint_address, 0) < 30:
                    return trade_bot.price_cache[mint_address]["price_usd"]
            
            # Token bilgilerini al
            token_info = await get_token_info(trade_bot, mint_address, force_update=True)
            if token_info and token_info["price_usd"] > 0:
                return token_info["price_usd"]
                
            trade_bot.update_log(
                mint_address,
                f"Fiyat alınamadı, tekrar deneniyor: {mint_address} (Deneme {attempts + 1}/{max_attempts})"
            )
            await asyncio.sleep(1)
            attempts += 1
        except Exception as e:
            trade_bot.update_log(
                mint_address,
                f"Fiyat alma hatası: {mint_address}, Hata: {e} (Deneme {attempts + 1}/{max_attempts})"
            )
            attempts += 1
    
    trade_bot.update_log(mint_address, f"Tüm denemeler başarısız, fiyat alınamadı: {mint_address}")
    return None


def force_price_update(trade_bot, mint_address):
    """
    Token fiyatını güç kullanarak günceller
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address (str): Token mint adresi
        
    Returns:
        float or None: Güncel fiyat veya None (başarısız ise)
    """
    try:
        # Rate limiter - çok fazla istek göndermemek için
        current_time = time.time()
        last_request = trade_bot._last_price_requests.get(mint_address, 0)
        
        if current_time - last_request < 10:
            return trade_bot.websocket_prices.get(mint_address)
            
        trade_bot._last_price_requests[mint_address] = current_time
        
        def fetch_price_from_multiple_sources():
            """Birden fazla kaynaktan fiyat çekmeyi deneyen fonksiyon"""
            try:
                # Sonuç değişkenleri
                success = False
                price_usd = None
                token_info = None
                error_messages = []
                
                # 1. Önce WebSocket fiyatını kontrol et (varsa ve yeni ise kullan)
                if mint_address in trade_bot.websocket_prices and trade_bot.websocket_active:
                    ws_price = trade_bot.websocket_prices.get(mint_address, 0)
                    ws_update_time = trade_bot.last_price_update.get(mint_address, 0)
                    
                    # WebSocket fiyatı yeterince yeni mi? (son 60 saniye içinde)
                    if ws_price > 0 and current_time - ws_update_time < 60:
                        # Düzgün bir WebSocket fiyatımız var
                        current_provider = 'WebSocket'
                        if trade_bot.root and hasattr(trade_bot, "DEBUG_MODE") and trade_bot.DEBUG_MODE:
                            log_to_file(f"Fiyat {current_provider}'dan alındı: {mint_address} - ${ws_price:.8f}")
                        
                        # Bu fiyatı döndürebiliriz ancak arka planda güncel fiyatları da kontrol edelim
                        price_usd = ws_price
                        success = True
                
                # 2. DexScreener API'yi dene
                try:
                    response = requests.get(
                        f"https://api.dexscreener.com/latest/dex/tokens/{mint_address}", 
                        timeout=3,
                        headers={
                            'User-Agent': 'TradeBot/1.0',
                            'Accept': 'application/json'
                        }
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    if data.get("pairs"):
                        pair = data["pairs"][0]
                        dex_price = float(pair.get("priceUsd", 0))
                        
                        if dex_price > 0:
                            # DexScreener'dan geçerli fiyat alındı
                            if trade_bot.root and hasattr(trade_bot, "DEBUG_MODE") and trade_bot.DEBUG_MODE:
                                log_to_file(f"Fiyat DexScreener'dan alındı: {mint_address} - ${dex_price:.8f}")
                            
                            # Tüm bilgileri çıkar
                            token_info = {
                                "symbol": pair.get("baseToken", {}).get("symbol", "Bilinmeyen"),
                                "price_usd": dex_price,
                                "liquidity_usd": float(pair.get("liquidity", {}).get("usd", 0)),
                                "market_cap": float(pair.get("marketCap", 0)),
                                "volume": float(pair.get("volume", {}).get("h24", 0))
                            }
                            
                            # Eğer WebSocket'ten fiyat almamışsak, bu fiyatı kullan
                            if not success:
                                price_usd = dex_price
                                success = True
                    else:
                        error_messages.append("DexScreener: Pair bulunamadı")
                except requests.RequestException as e:
                    error_messages.append(f"DexScreener: {str(e)}")
                except Exception as e:
                    error_messages.append(f"DexScreener Genel: {str(e)}")
                
                # 3. Jupiter API'yi dene (diğerleri başarısız olduysa veya token_info yoksa)
                if not success or token_info is None:
                    try:
                        # Jupiter API'den fiyat çek
                        quote_url = "https://quote-api.jup.ag/v6/quote"
                        params = {
                            "inputMint": "So11111111111111111111111111111111111111112",
                            "outputMint": mint_address,
                            "amount": 1000000000,  # 1 SOL
                            "slippageBps": 100
                        }
                        
                        response = requests.get(quote_url, params=params, timeout=3)
                        response.raise_for_status()
                        quote_data = response.json()
                        
                        # SOL fiyatını al
                        sol_price = 150.0  # Varsayılan
                        try:
                            sol_price_response = requests.get(
                                "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd", 
                                timeout=2
                            )
                            if sol_price_response.status_code == 200:
                                sol_price_data = sol_price_response.json()
                                sol_price = sol_price_data.get("solana", {}).get("usd", 150.0)
                        except:
                            # Varsayılan SOL fiyatını kullan
                            pass
                        
                        # Fiyat hesaplama
                        out_amount = float(quote_data.get("outAmount", 0))
                        jupiter_price = (out_amount / 1_000_000_000) * sol_price
                        
                        if jupiter_price > 0:
                            # Jupiter'dan geçerli fiyat alındı
                            if trade_bot.root and hasattr(trade_bot, "DEBUG_MODE") and trade_bot.DEBUG_MODE:
                                log_to_file(f"Fiyat Jupiter'dan alındı: {mint_address} - ${jupiter_price:.8f}")
                            
                            # Eğer DexScreener'dan token_info almamışsak, basit bir token_info oluştur
                            if token_info is None:
                                token_info = {
                                    "symbol": "Bilinmeyen",
                                    "price_usd": jupiter_price,
                                    "liquidity_usd": 0,
                                    "market_cap": 0,
                                    "volume": 0
                                }
                            
                            # Eğer henüz başarılı bir fiyat almamışsak, bu fiyatı kullan
                            if not success:
                                price_usd = jupiter_price
                                success = True
                    except requests.RequestException as e:
                        error_messages.append(f"Jupiter: {str(e)}")
                    except Exception as e:
                        error_messages.append(f"Jupiter Genel: {str(e)}")
                
                # Sonuçları işle
                if success and price_usd is not None:
                    # Cache'e her halükarda kaydet
                    if token_info is not None:
                        trade_bot.price_cache[mint_address] = token_info
                        trade_bot.last_price_update[mint_address] = current_time
                    
                    # Fiyat geçmişine ekle
                    from datetime import datetime
                    trade_bot.price_history[mint_address].append({
                        "timestamp": datetime.now(),
                        "price_usd": price_usd
                    })
                    
                    # Bu fiyatı WebSocket fiyatı olarak kullan
                    trade_bot.websocket_prices[mint_address] = price_usd
                    
                    # İlgili kuyruklara ekle ve analiz et
                    trade_bot.price_queue.put_async((mint_address, price_usd))
                    
                    # Analyzer'a bildir
                    current_time = datetime.now()
                    trade_bot.analyzer.update_price_history(mint_address, price_usd, current_time)
                    
                    return price_usd
                else:
                    # Tüm yöntemler başarısız oldu
                    if error_messages:
                        error_summary = " | ".join(error_messages)
                        log_to_file(f"Fiyat güncellenemedi ({mint_address}): {error_summary}")
                    return None
            
            except Exception as e:
                log_to_file(f"Fiyat güncelleme genel hatası: {mint_address} - {e}")
                return None
        
        # Fiyat güncelleme işlemini arka planda başlat
        update_thread = threading.Thread(target=fetch_price_from_multiple_sources, daemon=True)
        update_thread.start()
        
        # Mevcut fiyatı hemen döndür (varsa)
        return trade_bot.websocket_prices.get(mint_address)
    
    except Exception as e:
        logger.error(f"Force price update fonksiyonu hatası: {e}")
        return None


async def get_market_candles(trade_bot, mint_address, interval="1m", limit=60):
    """
    Belirli bir token için mum verilerini getirir.
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address (str): Token mint adresi
        interval (str): Mum aralığı (1m, 5m, 15m, 1h, 4h, 1d)
        limit (int): Mum sayısı
        
    Returns:
        list: Mum verileri listesi
    """
    try:
        # DexScreener API
        url = f"https://api.dexscreener.com/latest/dex/tokens/{mint_address}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as response:
                if response.status != 200:
                    logger.warning(f"DexScreener API hatası: {response.status}")
                    return []
                
                data = await response.json()
                
                if "pairs" not in data or not data["pairs"]:
                    logger.warning(f"Token için pair bulunamadı: {mint_address}")
                    return []
                
                pair = data["pairs"][0]
                pair_address = pair.get("pairAddress")
                
                if not pair_address:
                    logger.warning(f"Pair adresi bulunamadı: {mint_address}")
                    return []
                
                # Mum verileri için API
                candles_url = f"https://open-api.dextools.io/free/v2/pair/{pair_address}/candles"
                params = {
                    "interval": interval,
                    "limit": limit
                }
                headers = {
                    "X-API-Key": "demo-api-key",  # Ücretsiz demo anahtar
                    "Accept": "application/json"
                }
                
                try:
                    async with session.get(candles_url, params=params, headers=headers, timeout=5) as candles_response:
                        if candles_response.status != 200:
                            logger.warning(f"Mum verisi API hatası: {candles_response.status}")
                            return await _simulate_market_data(mint_address, interval, limit)
                        
                        candles_data = await candles_response.json()
                        
                        if "data" not in candles_data or not candles_data["data"]:
                            logger.warning(f"Mum veri bulunamadı: {mint_address}")
                            return await _simulate_market_data(mint_address, interval, limit)
                        
                        return candles_data["data"]
                except Exception as e:
                    logger.error(f"Mum verisi API hatası: {e}")
                    return await _simulate_market_data(mint_address, interval, limit)
    
    except Exception as e:
        logger.error(f"Piyasa verisi alma hatası: {e}")
        return await _simulate_market_data(mint_address, interval, limit)


async def _simulate_market_data(mint_address, interval, limit):
    """
    Gerçek veri alınamadığında simüle edilmiş piyasa verisi oluşturur.
    
    Args:
        mint_address (str): Token mint adresi
        interval (str): Mum aralığı
        limit (int): Mum sayısı
        
    Returns:
        list: Simüle edilmiş mum verileri
    """
    import random
    import numpy as np
    from datetime import datetime, timedelta
    
    logger.info(f"Simüle edilmiş veri oluşturuluyor: {mint_address}")
    
    # Aralığa göre süre belirle
    if interval == "1m":
        delta = timedelta(minutes=1)
    elif interval == "5m":
        delta = timedelta(minutes=5)
    elif interval == "15m":
        delta = timedelta(minutes=15)
    elif interval == "1h":
        delta = timedelta(hours=1)
    elif interval == "4h":
        delta = timedelta(hours=4)
    else:  # "1d"
        delta = timedelta(days=1)
    
    # Rassal başlangıç fiyatı (0.00001 - 0.1 arası)
    base_price = random.uniform(0.00001, 0.1)
    
    # Rassal volatilite (düşük - yüksek)
    volatility = random.uniform(0.01, 0.1)
    
    # Brownian motion ile fiyat simülasyonu
    price_changes = np.random.normal(0, volatility, limit)
    prices = [max(0.00000001, base_price * (1 + sum(price_changes[:i+1]))) for i in range(limit)]
    
    # Hacim simülasyonu
    base_volume = random.uniform(1000, 100000)
    volumes = [max(100, base_volume * (1 + random.uniform(-0.5, 0.5))) for _ in range(limit)]
    
    # Veri noktası oluşturma
    now = datetime.now()
    data = []
    
    for i in range(limit):
        timestamp = int((now - delta * (limit - i - 1)).timestamp() * 1000)
        open_price = prices[i] * (1 + random.uniform(-0.01, 0.01))
        close_price = prices[i]
        high_price = max(open_price, close_price) * (1 + random.uniform(0, 0.02))
        low_price = min(open_price, close_price) * (1 - random.uniform(0, 0.02))
        
        data.append({
            "timestamp": timestamp,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "volume": volumes[i]
        })
    
    return data


async def get_top_tokens(limit=50, min_liquidity=10000):
    """
    En yüksek hacimli tokenleri getirir.
    
    Args:
        limit (int): Alınacak token sayısı
        min_liquidity (float): Minimum likidite (USD)
        
    Returns:
        list: Token listesi
    """
    try:
        # DexScreener API
        url = "https://api.dexscreener.com/latest/dex/tokens/trending"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as response:
                if response.status != 200:
                    logger.warning(f"DexScreener API hatası: {response.status}")
                    return []
                
                data = await response.json()
                
                if "pairs" not in data or not data["pairs"]:
                    logger.warning("Trending tokenler bulunamadı")
                    return []
                
                tokens = []
                for pair in data["pairs"][:limit]:
                    liquidity_usd = float(pair.get("liquidity", {}).get("usd", 0))
                    
                    if liquidity_usd >= min_liquidity:
                        tokens.append({
                            "mint": pair.get("baseToken", {}).get("address"),
                            "symbol": pair.get("baseToken", {}).get("symbol", "Bilinmeyen"),
                            "price_usd": float(pair.get("priceUsd", 0)),
                            "liquidity_usd": liquidity_usd,
                            "volume_24h": float(pair.get("volume", {}).get("h24", 0)),
                            "price_change_24h": float(pair.get("priceChange", {}).get("h24", 0))
                        })
                
                return tokens
    
    except Exception as e:
        logger.error(f"Top tokenler alma hatası: {e}")
        return []


async def get_new_listings(limit=20, min_liquidity=5000, max_age_hours=24):
    """
    Yeni listelenmiş tokenleri getirir.
    
    Args:
        limit (int): Alınacak token sayısı
        min_liquidity (float): Minimum likidite (USD)
        max_age_hours (int): Maksimum yaş (saat olarak)
        
    Returns:
        list: Token listesi
    """
    try:
        from datetime import datetime, timedelta
        
        # DexScreener API
        url = "https://api.dexscreener.com/latest/dex/tokens/solana"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as response:
                if response.status != 200:
                    logger.warning(f"DexScreener API hatası: {response.status}")
                    return []
                
                data = await response.json()
                
                if "pairs" not in data or not data["pairs"]:
                    logger.warning("Yeni tokenler bulunamadı")
                    return []
                
                # Şu anki zaman
                now = datetime.now()
                max_age = timedelta(hours=max_age_hours)
                
                # Yeni tokenleri filtrele
                new_tokens = []
                for pair in data["pairs"]:
                    try:
                        # Oluşturma zamanını kontrol et
                        created_at = datetime.fromtimestamp(pair.get("pairCreatedAt", 0) / 1000)
                        age = now - created_at
                        
                        liquidity_usd = float(pair.get("liquidity", {}).get("usd", 0))
                        
                        if age <= max_age and liquidity_usd >= min_liquidity:
                            new_tokens.append({
                                "mint": pair.get("baseToken", {}).get("address"),
                                "symbol": pair.get("baseToken", {}).get("symbol", "Bilinmeyen"),
                                "price_usd": float(pair.get("priceUsd", 0)),
                                "liquidity_usd": liquidity_usd,
                                "volume_24h": float(pair.get("volume", {}).get("h24", 0)),
                                "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S"),
                                "age_hours": age.total_seconds() / 3600
                            })
                            
                            if len(new_tokens) >= limit:
                                break
                    except Exception as e:
                        logger.debug(f"Token işleme hatası: {e}")
                        continue
                
                return new_tokens
    
    except Exception as e:
        logger.error(f"Yeni listelemeler alma hatası: {e}")
        return []
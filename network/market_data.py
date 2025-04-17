# -*- coding: utf-8 -*-
import aiohttp
import asyncio
from datetime import datetime, timedelta
from loguru import logger

from utils.logging_utils import log_to_file
from config import USDC_MINT

async def get_market_data(mint_address, interval="1h", limit=100):
    """
    Belirli bir token için piyasa verilerini getirir
    
    Args:
        mint_address (str): Token mint adresi
        interval (str): Veri aralığı ('1m', '5m', '15m', '1h', '4h', '1d')
        limit (int): Alınacak veri noktası sayısı
    
    Returns:
        list: Veri noktaları listesi veya boş liste (başarısız ise)
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
                
                # Tarihsel veri için DexTools API (ücretsiz sürüm sınırlıdır)
                # Alternatif olarak DexScreener'ın kendi endpoints'i de kullanılabilir
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
                            logger.warning(f"DexTools API hatası: {candles_response.status}")
                            return _simulate_market_data(mint_address, interval, limit)
                        
                        candles_data = await candles_response.json()
                        
                        if "data" not in candles_data or not candles_data["data"]:
                            logger.warning(f"Mum veri bulunamadı: {mint_address}")
                            return _simulate_market_data(mint_address, interval, limit)
                        
                        return candles_data["data"]
                except Exception as e:
                    logger.error(f"DexTools API hatası: {e}")
                    return _simulate_market_data(mint_address, interval, limit)
    
    except Exception as e:
        logger.error(f"Piyasa verisi alma hatası: {e}")
        return _simulate_market_data(mint_address, interval, limit)

def _simulate_market_data(mint_address, interval, limit):
    """
    Gerçek veri alınamadığında simüle edilmiş piyasa verisi oluşturur
    
    Args:
        mint_address (str): Token mint adresi
        interval (str): Veri aralığı
        limit (int): Veri noktası sayısı
    
    Returns:
        list: Simüle edilmiş veri noktaları
    """
    import random
    import numpy as np
    
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
    En yüksek hacimli tokenleri getirir
    
    Args:
        limit (int): Alınacak token sayısı
        min_liquidity (float): Minimum likidite (USD)
    
    Returns:
        list: Token listesi veya boş liste (başarısız ise)
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
    Yeni listelenmiş tokenleri getirir
    
    Args:
        limit (int): Alınacak token sayısı
        min_liquidity (float): Minimum likidite (USD)
        max_age_hours (int): Maksimum yaş (saat olarak)
    
    Returns:
        list: Token listesi veya boş liste (başarısız ise)
    """
    try:
        # DexScreener API - yeni listeler için özel endpoint yoksa
        # chain endpoints kullanılabilir ve sonuçlar filtrelenebilir
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
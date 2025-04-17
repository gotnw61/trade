# -*- coding: utf-8 -*-
import time
import requests
import asyncio
import aiohttp
import base64
from solders.transaction import Transaction
from loguru import logger

from utils.logging_utils import log_to_file
from config import (
    trade_settings, SOLANA_RPC_URL, USDC_MINT, SLIPPAGE_BPS
)

# Token bilgisi cache'i (performans için)
_token_cache = {}
_cache_time = {}

async def get_token_info(mint_address, force_update=False):
    """
    Belirli bir token için bilgileri getirir
    
    Args:
        mint_address (str): Token mint adresi
        force_update (bool): Her zaman güncel veri almak için
        
    Returns:
        dict: Token bilgileri veya None (başarısız ise)
    """
    now = time.time()
    if not force_update and mint_address in _token_cache and now - _cache_time.get(mint_address, 0) < 30:
        return _token_cache[mint_address]
    
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
                        _token_cache[mint_address] = info
                        _cache_time[mint_address] = now
                        
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
                sol_price = 150.0  # Varsayılan
                try:
                    sol_price_response = await session.get(
                        "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd",
                        timeout=2
                    )
                    if sol_price_response.status == 200:
                        sol_price_data = await sol_price_response.json()
                        sol_price = sol_price_datarym.get("solana", {}).get("usd", 150.0)
                except:
                    pass
                
                # Fiyat hesapla
                price_usd = (float(quote_data.get("outAmount", 0)) / 1_000_000_000) * sol_price
                
                if price_usd < 0.0000001 or price_usd > 10000:
                    return None
                    
                info = {
                    "symbol": "Bilinmeyen",
                    "price_usd": price_usd,
                    "liquidity_usd": 0,
                    "market_cap": 0,
                    "volume": 0
                }
                
                # Cache güncelleme
                _token_cache[mint_address] = info
                _cache_time[mint_address] = now
                
                return info
    
    except Exception as e:
        logger.error(f"Jupiter API fiyat alma hatası: {e}")
        return None

async def get_token_price(mint_address, force_update=False):
    """
    Belirli bir token için fiyat bilgisini getirir
    
    Args:
        mint_address (str): Token mint adresi
        force_update (bool): Her zaman güncel veri almak için
        
    Returns:
        float: Token fiyatı veya None (başarısız ise)
    """
    attempts = 0
    max_attempts = 5
    
    while attempts < max_attempts:
        try:
            token_info = await get_token_info(mint_address, force_update=force_update)
            if token_info and token_info["price_usd"] > 0:
                return token_info["price_usd"]
                
            logger.warning(f"Fiyat alınamadı, tekrar deneniyor: {mint_address} (Deneme {attempts + 1}/{max_attempts})")
            await asyncio.sleep(1)
            attempts += 1
        except Exception as e:
            logger.error(f"Fiyat alma hatası: {mint_address}, Hata: {e} (Deneme {attempts + 1}/{max_attempts})")
            attempts += 1
    
    logger.error(f"Tüm denemeler başarısız, fiyat alınamadı: {mint_address}")
    return None

async def execute_swap(wallet, mint_address, amount, buy=True):
    """
    Token alım/satım işlemini gerçekleştirir
    
    Args:
        wallet: Cüzdan yöneticisi
        mint_address (str): İşlem yapılacak token'ın mint adresi
        amount (float): İşlem miktarı (SOL veya token miktarı)
        buy (bool): True ise alım, False ise satım işlemi
    
    Returns:
        str: İşlem hash'i veya None (başarısız ise)
    """
    try:
        # Simülasyon modunda ise sadece bir simulasyon gerçekleştir
        if trade_settings["simulation_mode"]:
            logger.info(f"💡 Simülasyon modu: {'Alım' if buy else 'Satım'} simulasyonu")
            # Rastgele bir işlem hash'i üret
            import random, string
            tx_hash = ''.join(random.choices(string.ascii_lowercase + string.digits, k=43))
            logger.info(f"✅ Simüle edilmiş işlem hash: {tx_hash}")
            return tx_hash
        
        # Gerçek işlem için
        logger.info(f"🔄 {'Alım' if buy else 'Satım'} işlemi gerçekleştiriliyor")
        
        # Jupiter API kullanarak swap işlemi
        async with aiohttp.ClientSession() as session:
            # Quote API'den fiyat teklifi alınıyor
            quote_url = "https://quote-api.jup.ag/v6/quote"
            
            # Alım veya satım durumuna göre parametreleri ayarla
            if buy:
                input_mint = "So11111111111111111111111111111111111111112"  # SOL
                output_mint = mint_address
                swap_amount = int(amount * 1_000_000_000)  # SOL -> Lamports
            else:
                input_mint = mint_address
                output_mint = "So11111111111111111111111111111111111111112"  # SOL
                
                # Token miktarı hesapla
                if hasattr(wallet, 'positions') and mint_address in wallet.positions:
                    token_amount = wallet.positions[mint_address]["remaining_token_amount"]
                    # Yüzde hesaplama
                    if amount < token_amount:
                        percentage = amount / wallet.positions[mint_address]["remaining_amount"]
                        swap_amount = int(token_amount * percentage)
                    else:
                        swap_amount = int(token_amount)
                else:
                    # Manuel satış için
                    swap_amount = int(amount)
            
            # Slippage değerini ayarla
            slippage = trade_settings.get("slippage_tolerance", 1) * 100  # %1 -> 100 bps
            
            params = {
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": swap_amount,
                "slippageBps": slippage
            }
            
            # Quote API'ye istek gönder
            async with session.get(quote_url, params=params, timeout=5) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"❌ Quote API hatası: {error_text}")
                    return None
                
                quote_data = await response.json()
                
                if "error" in quote_data:
                    logger.error(f"❌ Quote hatası: {quote_data['error']}")
                    return None
            
            # Swap API'den işlem verilerini al
            swap_url = "https://quote-api.jup.ag/v6/swap"
            
            # Aktif cüzdan bilgilerini al
            if not hasattr(wallet, 'wallets') or not hasattr(wallet, 'active_wallet_index') or wallet.active_wallet_index == -1:
                logger.error("❌ Aktif cüzdan yok")
                return None
            
            wallet_pubkey = str(wallet.wallets[wallet.active_wallet_index]["keypair"].pubkey())
            
            swap_body = {
                "quoteResponse": quote_data,
                "userPublicKey": wallet_pubkey,
                "wrapUnwrapSOL": True
            }
            
            # Swap API'ye istek gönder
            async with session.post(swap_url, json=swap_body) as swap_response:
                if swap_response.status != 200:
                    error_text = await swap_response.text()
                    logger.error(f"❌ Swap API hatası: {error_text}")
                    return None
                
                swap_data = await swap_response.json()
                
                if "error" in swap_data:
                    logger.error(f"❌ Swap hatası: {swap_data['error']}")
                    return None
            
            # Transaction'ı çöz ve imzala
            keypair = wallet.wallets[wallet.active_wallet_index]["keypair"]
            client = wallet.client
            
            # Base64'ten binary'ye çevir
            import base64
            tx_binary = base64.b64decode(swap_data["swapTransaction"])
            
            # Transaction'ı deserialize et
            tx = Transaction.from_bytes(tx_binary)
            
            # İşlemi imzala
            signed_tx = tx.sign([keypair])
            
            # İşlemi gönder
            from solana.rpc.types import TxOpts
            tx_opts = TxOpts(skip_preflight=False)
            result = await client.send_transaction(signed_tx, opts=tx_opts)
            
            tx_hash = result.value
            logger.info(f"✅ İşlem gönderildi: {tx_hash}")
            
            # İşlemin onaylanmasını bekle
            logger.info("⏳ İşlem onayı bekleniyor...")
            
            # En fazla 30 saniye bekle
            for _ in range(30):
                try:
                    # İşlem durumunu kontrol et
                    status_response = await client.get_transaction(tx_hash, max_supported_transaction_version=0)
                    if status_response.value is not None:
                        if status_response.value.meta and status_response.value.meta.err is None:
                            logger.info("✅ İşlem onaylandı!")
                            return tx_hash
                        else:
                            logger.error(f"❌ İşlem reddedildi: {status_response.value.meta.err}")
                            return None
                except Exception as status_error:
                    # Hatayı görmezden gel ve beklemeye devam et
                    pass
                    
                # 1 saniye bekle
                await asyncio.sleep(1)
            
            # Zaman aşımı
            logger.warning("⚠️ İşlem durum sorgusu zaman aşımına uğradı, ancak işlem gönderildi")
            return tx_hash
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"❌ Swap işlemi hatası: {e}")
        log_to_file(f"Swap hatası ayrıntıları: {error_details}")
        return None

async def get_token_transactions(mint_address, limit=50):
    """
    Belirli bir token için son işlemleri getirir
    
    Args:
        mint_address (str): Token mint adresi
        limit (int): Alınacak işlem sayısı
    
    Returns:
        list: İşlem listesi veya boş liste (başarısız ise)
    """
    try:
        # Solana RPC API
        rpc_url = SOLANA_RPC_URL
        
        # Programatik olarak token işlemlerini almak için account info
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": [
                mint_address,
                {
                    "limit": limit
                }
            ]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(rpc_url, json=payload) as response:
                if response.status != 200:
                    return []
                
                result = await response.json()
                if "result" not in result:
                    return []
                
                signatures = [tx["signature"] for tx in result["result"]]
                return signatures
    except Exception as e:
        logger.error(f"Token işlemleri alma hatası: {e}")
        return []

async def fetch_transaction_details(tx_hash):
    """
    Belirli bir işlemin detaylarını getirir
    
    Args:
        tx_hash (str): İşlem hash'i
    
    Returns:
        dict: İşlem detayları veya None (başarısız ise)
    """
    try:
        # Solana RPC API
        rpc_url = SOLANA_RPC_URL
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTransaction",
            "params": [
                tx_hash,
                {"encoding": "json", "maxSupportedTransactionVersion": 0}
            ]
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(rpc_url, json=payload) as response:
                if response.status != 200:
                    return None
                
                result = await response.json()
                
                if "result" not in result or not result["result"]:
                    return None
                
                return result["result"]
    except Exception as e:
        logger.error(f"İşlem detayları alma hatası: {e}")
        return None
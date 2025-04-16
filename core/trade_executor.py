# -*- coding: utf-8 -*-
"""
İşlem yürütme modülü - alım/satım işlemlerini gerçekleştirir
"""

import base64
import random
import string
import aiohttp
import asyncio
from loguru import logger
from solders.transaction import Transaction
from solana.rpc.types import TxOpts

from gotnw_tradebot.config import trade_settings
from gotnw_tradebot.utils.logging_utils import log_to_file


async def execute_swap(trade_bot, mint_address, amount, buy=True):
    """
    Token alım/satım işlemini gerçekleştirir.
    
    Args:
        trade_bot: TradeBot nesnesi
        mint_address (str): İşlem yapılacak token'ın mint adresi
        amount (float): İşlem miktarı (SOL veya token miktarı)
        buy (bool): True ise alım, False ise satım işlemi
    
    Returns:
        str: İşlem hash'i veya None (başarısız ise)
    """
    try:
        # Simülasyon modunda ise sadece bir simulasyon gerçekleştir
        if trade_settings["simulation_mode"]:
            trade_bot.update_log(mint_address, f"💡 Simülasyon modu: {'Alım' if buy else 'Satım'} simulasyonu")
            # Rastgele bir işlem hash'i üret
            tx_hash = ''.join(random.choices(string.ascii_lowercase + string.digits, k=43))
            trade_bot.update_log(mint_address, f"✅ Simüle edilmiş işlem hash: {tx_hash}")
            return tx_hash
        
        # Gerçek işlem için
        trade_bot.update_log(mint_address, f"🔄 {'Alım' if buy else 'Satım'} işlemi gerçekleştiriliyor")
        
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
                if mint_address in trade_bot.positions:
                    token_amount = trade_bot.positions[mint_address]["remaining_token_amount"]
                    # Yüzde hesaplama
                    if amount < trade_bot.positions[mint_address]["remaining_amount"]:
                        percentage = amount / trade_bot.positions[mint_address]["remaining_amount"]
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
                    trade_bot.update_log(mint_address, f"❌ Quote API hatası: {error_text}")
                    return None
                
                quote_data = await response.json()
                
                if "error" in quote_data:
                    trade_bot.update_log(mint_address, f"❌ Quote hatası: {quote_data['error']}")
                    return None
            
            # Swap API'den işlem verilerini al
            swap_url = "https://quote-api.jup.ag/v6/swap"
            
            # Aktif cüzdan bilgilerini al
            if trade_bot.wallet.active_wallet_index == -1:
                trade_bot.update_log(mint_address, "❌ Aktif cüzdan yok")
                return None
            
            wallet_pubkey = str(trade_bot.wallet.wallets[trade_bot.wallet.active_wallet_index]["keypair"].pubkey())
            
            swap_body = {
                "quoteResponse": quote_data,
                "userPublicKey": wallet_pubkey,
                "wrapUnwrapSOL": True
            }
            
            # Swap API'ye istek gönder
            async with session.post(swap_url, json=swap_body, timeout=5) as swap_response:
                if swap_response.status != 200:
                    error_text = await swap_response.text()
                    trade_bot.update_log(mint_address, f"❌ Swap API hatası: {error_text}")
                    return None
                
                swap_data = await swap_response.json()
                
                if "error" in swap_data:
                    trade_bot.update_log(mint_address, f"❌ Swap hatası: {swap_data['error']}")
                    return None
            
            # Transaction'ı çöz ve imzala
            keypair = trade_bot.wallet.wallets[trade_bot.wallet.active_wallet_index]["keypair"]
            client = trade_bot.wallet.client
            
            # Base64'ten binary'ye çevir
            tx_binary = base64.b64decode(swap_data["swapTransaction"])
            
            # Transaction'ı deserialize et
            tx = Transaction.from_bytes(tx_binary)
            
            # İşlemi imzala
            signed_tx = tx.sign([keypair])
            
            # İşlemi gönder
            tx_opts = TxOpts(skip_preflight=False)
            result = await client.send_transaction(signed_tx, opts=tx_opts)
            
            tx_hash = result.value
            trade_bot.update_log(mint_address, f"✅ İşlem gönderildi: {tx_hash}")
            
            # İşlemin onaylanmasını bekle
            trade_bot.update_log(mint_address, "⏳ İşlem onayı bekleniyor...")
            
            # En fazla 30 saniye bekle
            for _ in range(30):
                try:
                    # İşlem durumunu kontrol et
                    status_response = await client.get_transaction(tx_hash, max_supported_transaction_version=0)
                    if status_response.value is not None:
                        if status_response.value.meta and status_response.value.meta.err is None:
                            trade_bot.update_log(mint_address, "✅ İşlem onaylandı!")
                            return tx_hash
                        else:
                            trade_bot.update_log(mint_address, f"❌ İşlem reddedildi: {status_response.value.meta.err}")
                            return None
                except Exception as status_error:
                    # Hatayı görmezden gel ve beklemeye devam et
                    pass
                    
                # 1 saniye bekle
                await asyncio.sleep(1)
            
            # Zaman aşımı
            trade_bot.update_log(mint_address, "⚠️ İşlem durum sorgusu zaman aşımına uğradı, ancak işlem gönderildi")
            return tx_hash
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        trade_bot.update_log(mint_address, f"❌ Swap işlemi hatası: {e}")
        log_to_file(f"Swap hatası ayrıntıları: {error_details}")
        return None


async def estimate_transaction_fee(trade_bot, transaction):
    """
    İşlem ücretini tahmin eder.
    
    Args:
        trade_bot: TradeBot nesnesi
        transaction (Transaction): İşlem
        
    Returns:
        int: Tahmini işlem ücreti (lamports)
    """
    try:
        # Ücreti tahmin et
        response = await trade_bot.client.get_fee_for_message(transaction.message)
        
        if response.value is not None:
            logger.debug(f"Tahmini işlem ücreti: {response.value} lamports")
            return response.value
        
        # Varsayılan değeri döndür
        default_fee = 5000
        logger.debug(f"Ücret tahmini alınamadı, varsayılan değer kullanılıyor: {default_fee} lamports")
        return default_fee
    
    except Exception as e:
        logger.error(f"İşlem ücreti tahmin hatası: {e}")
        # Varsayılan değeri döndür
        return 5000


async def check_transaction_status(trade_bot, tx_signature, max_retries=30, sleep_seconds=1):
    """
    İşlem durumunu kontrol eder
    
    Args:
        trade_bot: TradeBot nesnesi
        tx_signature (str): İşlem imzası
        max_retries (int): Maksimum deneme sayısı
        sleep_seconds (int): Denemeler arası bekleme süresi (saniye)
        
    Returns:
        dict: İşlem durumu
    """
    for i in range(max_retries):
        try:
            response = await trade_bot.client.get_transaction(tx_signature, max_supported_transaction_version=0)
            
            if response.value is not None:
                meta = response.value.meta
                error = meta.err if meta else None
                
                if error is None:
                    logger.info(f"İşlem başarılı: {tx_signature}")
                    return {
                        "status": "success",
                        "signature": tx_signature,
                        "confirmations": response.value.slot,
                        "error": None
                    }
                else:
                    logger.error(f"İşlem başarısız: {tx_signature}, Hata: {error}")
                    return {
                        "status": "error",
                        "signature": tx_signature,
                        "confirmations": None,
                        "error": str(error)
                    }
            
        except Exception as e:
            if i == max_retries - 1:
                logger.error(f"İşlem durumu kontrolü başarısız: {e}")
                return {
                    "status": "unknown",
                    "signature": tx_signature,
                    "confirmations": None,
                    "error": str(e)
                }
        
        await asyncio.sleep(sleep_seconds)
    
    logger.warning(f"İşlem durumu belirsiz: {tx_signature}")
    return {
        "status": "timeout",
        "signature": tx_signature,
        "confirmations": None,
        "error": f"İşlem {max_retries} denemede onaylanmadı"
    }


async def build_swap_transaction(trade_bot, input_mint, output_mint, amount, slippage):
    """
    Swap işlemi için transaction oluşturur.
    
    Args:
        trade_bot: TradeBot nesnesi
        input_mint (str): Giriş token mint adresi
        output_mint (str): Çıkış token mint adresi
        amount (int): İşlem miktarı (atomik birimde)
        slippage (int): Slippage bps değeri
        
    Returns:
        dict or None: Transaction verisi veya None (başarısız ise)
    """
    try:
        # Fiyat teklifi alma
        quote_url = "https://quote-api.jup.ag/v6/quote"
        
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": amount,
            "slippageBps": slippage
        }
        
        async with aiohttp.ClientSession() as session:
            # Quote API'ye istek gönder
            async with session.get(quote_url, params=params, timeout=5) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Quote API hatası: {error_text}")
                    return None
                
                quote_data = await response.json()
                
                if "error" in quote_data:
                    logger.error(f"Quote hatası: {quote_data['error']}")
                    return None
                
                return quote_data
                
    except Exception as e:
        logger.error(f"Swap transaction oluşturma hatası: {e}")
        return None


async def convert_usdc_to_sol(trade_bot, usdc_amount):
    """
    USDC'yi SOL'a çevirir.
    
    Args:
        trade_bot: TradeBot nesnesi
        usdc_amount (float): USDC miktarı
        
    Returns:
        float or None: SOL miktarı veya None (başarısız ise)
    """
    try:
        from gotnw_tradebot.config import USDC_MINT
        
        # Fiyat teklifi alma
        quote_url = "https://quote-api.jup.ag/v6/quote"
        
        # USDC'nin atomik birimini hesapla (USDC 6 basamaklıdır)
        usdc_amount_atomic = int(usdc_amount * 1_000_000)
        
        params = {
            "inputMint": USDC_MINT,
            "outputMint": "So11111111111111111111111111111111111111112",  # SOL
            "amount": usdc_amount_atomic,
            "slippageBps": 50
        }
        
        async with aiohttp.ClientSession() as session:
            # Quote API'ye istek gönder
            async with session.get(quote_url, params=params, timeout=5) as response:
                if response.status != 200:
                    logger.error(f"USDC-SOL çevirme hatası: HTTP {response.status}")
                    return None
                
                quote_data = await response.json()
                
                if "error" in quote_data:
                    logger.error(f"USDC-SOL çevirme hatası: {quote_data['error']}")
                    return None
                
                # SOL miktarını al ve lamports'tan SOL'a çevir
                sol_amount = int(quote_data.get("outAmount", 0)) / 1_000_000_000
                return sol_amount
                
    except Exception as e:
        logger.error(f"USDC-SOL çevirme hatası: {e}")
        return None


async def convert_sol_to_usdc(trade_bot, sol_amount):
    """
    SOL'u USDC'ye çevirir.
    
    Args:
        trade_bot: TradeBot nesnesi
        sol_amount (float): SOL miktarı
        
    Returns:
        float or None: USDC miktarı veya None (başarısız ise)
    """
    try:
        from gotnw_tradebot.config import USDC_MINT
        
        # Fiyat teklifi alma
        quote_url = "https://quote-api.jup.ag/v6/quote"
        
        # SOL'un atomik birimini hesapla
        sol_amount_atomic = int(sol_amount * 1_000_000_000)
        
        params = {
            "inputMint": "So11111111111111111111111111111111111111112",  # SOL
            "outputMint": USDC_MINT,
            "amount": sol_amount_atomic,
            "slippageBps": 50
        }
        
        async with aiohttp.ClientSession() as session:
            # Quote API'ye istek gönder
            async with session.get(quote_url, params=params, timeout=5) as response:
                if response.status != 200:
                    logger.error(f"SOL-USDC çevirme hatası: HTTP {response.status}")
                    return None
                
                quote_data = await response.json()
                
                if "error" in quote_data:
                    logger.error(f"SOL-USDC çevirme hatası: {quote_data['error']}")
                    return None
                
                # USDC miktarını al ve atomik birimden USDC'ye çevir
                usdc_amount = int(quote_data.get("outAmount", 0)) / 1_000_000
                return usdc_amount
                
    except Exception as e:
        logger.error(f"SOL-USDC çevirme hatası: {e}")
        return None
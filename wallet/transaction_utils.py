# -*- coding: utf-8 -*-
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.transaction import Transaction
from solana.rpc.async_api import AsyncClient
from spl.token.instructions import get_associated_token_address, create_associated_token_account
from loguru import logger

from config import (
    RAYDIUM_PROGRAM_ID, RAYDIUM_AUTHORITY, TOKEN_PROGRAM_ID, SOLANA_RPC_URL
)

async def create_associated_token_account_if_needed(client, wallet_address, token_mint, payer_keypair):
    """
    Associated token hesabını kontrol eder, yoksa oluşturur
    
    Args:
        client (AsyncClient): Solana RPC client
        wallet_address (Pubkey): Cüzdan adresi
        token_mint (Pubkey): Token mint adresi
        payer_keypair (Keypair): Ödeme yapan cüzdan
        
    Returns:
        Pubkey: Associated token hesap adresi
    """
    try:
        # Associated token hesabını hesapla
        ata = get_associated_token_address(wallet_address, token_mint)
        
        # Hesap var mı kontrol et
        account_info = await client.get_account_info(ata)
        
        # Hesap yoksa oluştur
        if account_info.value is None:
            logger.info(f"Associated token hesabı oluşturuluyor: {token_mint}")
            
            # Talimatı oluştur
            create_ata_ix = create_associated_token_account(
                payer=payer_keypair.pubkey(),
                owner=wallet_address,
                mint=token_mint
            )
            
            # İşlemi oluştur
            tx = Transaction().add(create_ata_ix)
            
            # İşlemi imzala ve gönder
            response = await client.send_transaction(tx, payer_keypair)
            
            logger.info(f"Associated token hesabı oluşturuldu: {ata}, TX: {response.value}")
        else:
            logger.debug(f"Associated token hesabı zaten var: {ata}")
        
        return ata
    
    except Exception as e:
        logger.error(f"Associated token hesabı oluşturma hatası: {e}")
        raise

async def create_swap_instruction(client, input_mint, output_mint, amount, slippage, wallet_address=None):
    """
    Jupiter Swap için talimat oluşturur
    
    Args:
        client (AsyncClient): Solana RPC client
        input_mint (str): Giriş token mint adresi
        output_mint (str): Çıkış token mint adresi
        amount (int): Giriş token miktarı (lamports/atomik birim)
        slippage (int): Slippage (baz puan, 100 = %1)
        wallet_address (str, optional): Cüzdan adresi
        
    Returns:
        dict: Swap verileri
    """
    import aiohttp
    
    try:
        # Jupiter API kullanarak swap talimatı oluşturma
        quote_url = "https://quote-api.jup.ag/v6/quote"
        
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": amount,
            "slippageBps": slippage
        }
        
        async with aiohttp.ClientSession() as session:
            # Fiyat teklifi al
            async with session.get(quote_url, params=params, timeout=5) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Quote API hatası: {error_text}")
                    raise Exception(f"Quote API hatası: {response.status}")
                
                quote_data = await response.json()
                
                if "error" in quote_data:
                    logger.error(f"Quote hatası: {quote_data['error']}")
                    raise Exception(f"Quote hatası: {quote_data['error']}")
            
            # Swap talimatı al
            if wallet_address:
                swap_url = "https://quote-api.jup.ag/v6/swap"
                
                swap_body = {
                    "quoteResponse": quote_data,
                    "userPublicKey": wallet_address,
                    "wrapUnwrapSOL": True
                }
                
                async with session.post(swap_url, json=swap_body, timeout=5) as swap_response:
                    if swap_response.status != 200:
                        error_text = await swap_response.text()
                        logger.error(f"Swap API hatası: {error_text}")
                        raise Exception(f"Swap API hatası: {swap_response.status}")
                    
                    swap_data = await swap_response.json()
                    
                    if "error" in swap_data:
                        logger.error(f"Swap hatası: {swap_data['error']}")
                        raise Exception(f"Swap hatası: {swap_data['error']}")
                    
                    return swap_data
            
            # Sadece fiyat teklifi dönülüyor
            return quote_data
    
    except Exception as e:
        logger.error(f"Swap talimatı oluşturma hatası: {e}")
        raise

async def get_token_accounts(client, wallet_address):
    """
    Cüzdandaki tüm token hesaplarını getirir
    
    Args:
        client (AsyncClient): Solana RPC client
        wallet_address (Pubkey): Cüzdan adresi
        
    Returns:
        list: Token hesapları
    """
    try:
        # Token hesaplarını getir
        response = await client.get_token_accounts_by_owner(
            wallet_address,
            {"programId": Pubkey.from_string(TOKEN_PROGRAM_ID)}
        )
        
        if not response.value:
            return []
        
        token_accounts = []
        for account in response.value:
            pubkey = account.pubkey
            account_data = account.account.data
            
            # Token hesap verilerini ayrıştır
            mint = Pubkey.from_bytes(account_data[0:32])
            owner = Pubkey.from_bytes(account_data[32:64])
            amount = int.from_bytes(account_data[64:72], byteorder='little')
            
            token_accounts.append({
                "pubkey": str(pubkey),
                "mint": str(mint),
                "owner": str(owner),
                "amount": amount
            })
        
        return token_accounts
    
    except Exception as e:
        logger.error(f"Token hesapları alma hatası: {e}")
        return []

async def check_transaction_status(client, tx_signature, max_retries=30, sleep_seconds=1):
    """
    İşlem durumunu kontrol eder
    
    Args:
        client (AsyncClient): Solana RPC client
        tx_signature (str): İşlem imzası
        max_retries (int): Maksimum deneme sayısı
        sleep_seconds (int): Denemeler arası bekleme süresi (saniye)
        
    Returns:
        dict: İşlem durumu
    """
    import asyncio
    
    for i in range(max_retries):
        try:
            response = await client.get_transaction(tx_signature, max_supported_transaction_version=0)
            
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

async def estimate_transaction_fee(client, transaction):
    """
    İşlem ücretini tahmin eder
    
    Args:
        client (AsyncClient): Solana RPC client
        transaction (Transaction): İşlem
        
    Returns:
        int: Tahmini işlem ücreti (lamports)
    """
    try:
        # Ücreti tahmin et
        response = await client.get_fee_for_message(transaction.message)
        
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
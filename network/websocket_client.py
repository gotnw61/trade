# -*- coding: utf-8 -*-
import asyncio
import json
import random
import time
import websockets
from datetime import datetime
from loguru import logger

from config import HELIUS_WS_URL, RAYDIUM_PROGRAM_ID

async def start_websocket(handler, subscribed_tokens=None):
    """
    Gelişmiş, güvenilir WebSocket bağlantısı başlatır
    
    Args:
        handler (callable): Mesaj işleyici fonksiyonu
        subscribed_tokens (set, optional): Abone olunacak token listesi
        
    Returns:
        tuple: (websocket, subscription_ids)
    """
    uri = "wss://api.mainnet-beta.solana.com"
    max_retries = 20
    retry_delay_base = 2
    retry_count = 0
    
    # Bağlantı değişkenleri
    websocket = None
    websocket_active = False
    subscription_ids = {}
    
    if subscribed_tokens is None:
        subscribed_tokens = set()
    
    while retry_count < max_retries:
        try:
            # Bağlantı zamanını log'la
            current_time = datetime.now().strftime("%H:%M:%S")
            logger.warning(f"[{current_time}] WebSocket bağlantısı kuruluyor... (Deneme {retry_count + 1}/{max_retries})")
            
            # Gelişmiş bağlantı parametreleri
            websocket = await websockets.connect(
                uri,
                ping_interval=10,
                ping_timeout=30,
                close_timeout=30,
                max_size=20_000_000,
                max_queue=1024,
                compression=None
            )
            
            # Bağlantı başarılı, değişkenleri güncelle
            websocket_active = True
            websocket_last_active = time.time()
            logger.warning(f"[{current_time}] WebSocket bağlantısı başarıyla kuruldu!")
            
            # Tüm tokenlere abone ol
            for token_mint in subscribed_tokens:
                try:
                    subscription_msg = {
                        "jsonrpc": "2.0",
                        "id": random.randint(1000, 9999),
                        "method": "accountSubscribe",
                        "params": [
                            token_mint,
                            {
                                "encoding": "jsonParsed",
                                "commitment": "confirmed"
                            }
                        ]
                    }
                    await websocket.send(json.dumps(subscription_msg))
                    logger.debug(f"Token aboneliği: {token_mint}")
                except Exception as e:
                    logger.error(f"Token abonelik hatası: {e}")
            
            # Heartbeat task
            heartbeat_task = asyncio.create_task(
                _websocket_heartbeat(websocket, lambda: websocket_active)
            )
            
            # Ana mesaj alım döngüsü
            try:
                while websocket_active:
                    try:
                        # Mesaj bekle
                        message = await asyncio.wait_for(websocket.recv(), timeout=45)
                        websocket_last_active = time.time()
                        
                        # Mesajı işle
                        message_data = json.loads(message)
                        
                        # Mesaj türüne göre işle
                        await handler(message_data)
                        
                    except asyncio.TimeoutError:
                        # Mesaj alınamadı, bağlantıyı kontrol et
                        if time.time() - websocket_last_active > 50:
                            logger.warning("WebSocket mesaj alamadı, bağlantı kontrol ediliyor...")
                            try:
                                pong_waiter = await websocket.ping()
                                await asyncio.wait_for(pong_waiter, timeout=10)
                                logger.debug("Ping-pong başarılı, bağlantı aktif")
                                websocket_last_active = time.time()
                            except Exception as ping_err:
                                logger.warning(f"WebSocket ping başarısız: {ping_err}, yeniden bağlanılıyor...")
                                break
                    
                    except Exception as msg_error:
                        logger.warning(f"WebSocket mesaj işleme hatası: {msg_error}")
                        await asyncio.sleep(0.5)
            
            finally:
                # Heartbeat görevini temizle
                if heartbeat_task and not heartbeat_task.done():
                    heartbeat_task.cancel()
                    try:
                        await heartbeat_task
                    except asyncio.CancelledError:
                        pass
            
            # WebSocket bağlantısı kapandı, yeniden bağlanmayı dene
            websocket = None
            logger.warning("WebSocket bağlantısı kapandı, yeniden bağlanılıyor...")
        
        except (websockets.exceptions.ConnectionClosed, ConnectionResetError) as conn_error:
            error_code = getattr(conn_error, 'code', 0)
            error_reason = getattr(conn_error, 'reason', str(conn_error))
            logger.warning(f"WebSocket bağlantısı kapandı (Kod: {error_code}): {error_reason}")
            websocket = None
            retry_count += 1
        
        except Exception as e:
            logger.warning(f"WebSocket genel hatası: {str(e)}")
            websocket = None
            retry_count += 1
        
        # Üstel geri çekilme ile yeniden bağlanma gecikmesi
        real_delay = retry_delay_base * (2 ** (min(retry_count, 6) - 1))
        logger.warning(f"Yeniden bağlanmadan önce {real_delay} saniye bekleniyor...")
        await asyncio.sleep(real_delay)
    
    # Tüm yeniden bağlanma denemeleri başarısız oldu
    logger.error(f"WebSocket bağlantısı {max_retries} denemeden sonra kurulamadı.")
    
    return websocket, subscription_ids

async def _websocket_heartbeat(websocket, is_active_fn):
    """WebSocket bağlantısının canlı kalmasını sağlayan ayrı bir görev"""
    try:
        while is_active_fn():
            try:
                if hasattr(websocket, 'open') and websocket.open:
                    pong_waiter = await websocket.ping()
                    await asyncio.wait_for(pong_waiter, timeout=5)
                    logger.debug("Heartbeat ping başarılı")
                else:
                    logger.warning("Heartbeat: WebSocket kapalı, yeniden bağlanma gerekiyor")
                    break
            except Exception as e:
                logger.warning(f"Heartbeat ping hatası: {e}")
                break
            
            await asyncio.sleep(5)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Heartbeat görevinde beklenmeyen hata: {e}")
    
    logger.debug("Heartbeat görevi sonlandı")

async def stop_websocket(websocket):
    """
    WebSocket bağlantısını kapatır
    
    Args:
        websocket: WebSocket bağlantısı
    """
    try:
        if websocket:
            await websocket.close()
            logger.info("WebSocket bağlantısı kapatıldı")
    except Exception as e:
        logger.error(f"WebSocket kapatma hatası: {e}")

async def add_token_subscription(websocket, mint_address):
    """
    Belirli bir token için WebSocket aboneliği ekler
    
    Args:
        websocket: WebSocket bağlantısı
        mint_address (str): Token mint adresi
        
    Returns:
        int: Abonelik ID'si veya None (başarısız ise)
    """
    try:
        if not websocket or not websocket.open:
            logger.warning("WebSocket bağlantısı aktif değil, abonelik yapılamadı")
            return None
            
        subscription_msg = {
            "jsonrpc": "2.0",
            "id": random.randint(1000, 9999),
            "method": "accountSubscribe",
            "params": [
                mint_address,
                {
                    "encoding": "jsonParsed",
                    "commitment": "confirmed"
                }
            ]
        }
        
        await websocket.send(json.dumps(subscription_msg))
        logger.debug(f"Token aboneliği eklendi: {mint_address}")
        
        # Gerçek hayatta abonelik ID'si dönüş mesajından alınmalı
        return subscription_msg["id"]
    except Exception as e:
        logger.error(f"Token aboneliği ekleme hatası: {e}")
        return None

async def subscribe_to_program(websocket, program_id=RAYDIUM_PROGRAM_ID):
    """
    Belirli bir program için WebSocket aboneliği ekler
    
    Args:
        websocket: WebSocket bağlantısı
        program_id (str): Program ID
        
    Returns:
        int: Abonelik ID'si veya None (başarısız ise)
    """
    try:
        if not websocket or not websocket.open:
            logger.warning("WebSocket bağlantısı aktif değil, program aboneliği yapılamadı")
            return None
            
        subscription_msg = {
            "jsonrpc": "2.0",
            "id": random.randint(1000, 9999),
            "method": "programSubscribe",
            "params": [
                program_id,
                {
                    "encoding": "jsonParsed",
                    "commitment": "confirmed"
                }
            ]
        }
        
        await websocket.send(json.dumps(subscription_msg))
        logger.debug(f"Program aboneliği eklendi: {program_id}")
        
        return subscription_msg["id"]
    except Exception as e:
        logger.error(f"Program aboneliği ekleme hatası: {e}")
        return None
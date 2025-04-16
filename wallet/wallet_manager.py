# -*- coding: utf-8 -*-
import asyncio
import base58
import os
import json
import aiohttp
from datetime import datetime, timedelta
from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import Transaction  # solana.transaction yerine solders.transaction kullanıyoruz
from spl.token.instructions import get_associated_token_address
from spl.token.instructions import create_associated_token_account
from loguru import logger

from gotnw_tradebot.utils.logging_utils import log_to_file
from gotnw_tradebot.utils.console_utils import animated_text
from gotnw_tradebot.config import trade_settings, WALLET_DATA_FILE, SOLANA_RPC_URL, TOKEN_PROGRAM_ID

class WalletManager:
    """
    Solana cüzdan yönetimi için sınıf
    """
    def __init__(self):
        """
        WalletManager sınıfını başlat
        """
        self.client = AsyncClient(
            "https://api.mainnet-beta.solana.com", timeout=10)
        self.wallets = []
        self.active_wallet_index = -1
        self.trade_bot = None  # Added to reference trade_bot for state saving
        self.wallet_address = None
        self.keypair = None
        self.rpc_client = AsyncClient(SOLANA_RPC_URL)

        # Cüzdanları otomatik olarak yüklemeye çalış
        try:
            asyncio.create_task(self.load_wallets())
        except Exception as e:
            logger.error(f"Cüzdan yükleme hatası: {e}")

    async def connect_wallet(self, private_key):
        """
        Yeni bir cüzdanı bağlar
        
        Args:
            private_key (str): Cüzdan private key'i
            
        Returns:
            str: Sonuç mesajı
        """
        logger.info(f"Cüzdan bağlama girişimi başlatıldı...")
        try:
            # Boş veya çok kısa private key kontrolü
            if not private_key or len(private_key.strip()) < 32:
                message = "❌ Geçersiz özel anahtar (çok kısa)"
                logger.error(message)
                return message
                
            logger.debug(f"Base58 decode işlemi yapılıyor...")
            try:
                seed_bytes = base58.b58decode(private_key)
                logger.debug(f"Private key uzunluğu: {len(seed_bytes)} byte")
            except Exception as decode_error:
                message = f"❌ Base58 anahtar çözme hatası: {str(decode_error)}"
                logger.error(message)
                return message
            
            logger.debug(f"Keypair oluşturuluyor...")
            try:
                # from_bytes yerine from_seed kullan ve sadece ilk 32 byte'ı al
                keypair = Keypair.from_seed(seed_bytes[:32])
                pubkey = str(keypair.pubkey())
                logger.info(f"Pubkey oluşturuldu: {pubkey}")
            except Exception as keypair_error:
                logger.error(f"Keypair oluşturma hatası: {str(keypair_error)}")
                import traceback
                traceback.print_exc()
                message = f"❌ Keypair oluşturma hatası: {str(keypair_error)}"
                logger.error(message)
                return message
            
            # Wallet listesine ekle
            self.wallets.append({"keypair": keypair, "connected": True})
            self.active_wallet_index = len(self.wallets) - 1
            
            # Aktif cüzdan bilgilerini güncelle
            self.wallet_address = keypair.pubkey()
            self.keypair = keypair
            
            message = f"✅ Cüzdan bağlandı: {pubkey}"
            logger.info(message)
            
            try:
                # Cüzdanları kaydet
                logger.debug("Cüzdanlar kaydediliyor...")
                await self.save_wallets()
                logger.info("Cüzdanlar kaydedildi.")
                
                # Trade bot state'i kaydet
                if hasattr(self, 'trade_bot') and self.trade_bot and hasattr(self.trade_bot, 'save_state'):
                    logger.debug("Trade bot durumu kaydediliyor...")
                    await self.trade_bot.save_state()
                    logger.info("Trade bot durumu kaydedildi.")
            except Exception as save_error:
                logger.error(f"Cüzdan/durum kaydetme hatası (bağlantı etkilenmedi): {str(save_error)}")
                
            return message
        except Exception as e:
            import traceback
            traceback.print_exc()
            message = f"❌ Cüzdan bağlanamadı: {str(e)}"
            logger.error(message)
            return message

    async def switch_wallet(self, index):
        """
        Başka bir cüzdana geçiş yapar
        
        Args:
            index (int): Cüzdan indeksi
            
        Returns:
            str: Sonuç mesajı
        """
        try:
            if 0 <= index < len(self.wallets):
                self.active_wallet_index = index
                
                # Aktif cüzdan bilgilerini güncelle
                keypair = self.wallets[index]['keypair']
                self.wallet_address = keypair.pubkey()
                self.keypair = keypair
                
                message = f"✅ Cüzdan değiştirildi: {self.wallets[index]['keypair'].pubkey()}"
                animated_text(message)
                logger.info(message)
                
                # Cüzdanları kaydet
                await self.save_wallets()
                
                return message
            return "❌ Geçersiz cüzdan indeksi"
        except Exception as e:
            logger.error(f"❌ Cüzdan değiştirilemedi: {e}")
            return f"❌ Cüzdan değiştirilemedi: {e}"

    async def get_balance(self):
        """
        Aktif cüzdanın bakiyesini getirir
        
        Returns:
            float: Bakiye (SOL)
        """
        if trade_settings["simulation_mode"]:
            return trade_settings["simulation_balance"]
        
        if self.active_wallet_index == -1:
            return 0.0
        
        try:
            # Doğrudan value'yu almak yerine await kullanın
            balance_response = await self.client.get_balance(
                self.wallets[self.active_wallet_index]["keypair"].pubkey()
            )
            return balance_response.value / 1_000_000_000
        except Exception as e:
            log_to_file(f"Bakiye alınamadı: {e}")
            logger.error(f"Bakiye alınamadı: {e}")
            return 0.0

    async def save_wallets(self):
        """
        Cüzdan bilgilerini ayrı bir dosyaya kaydet
        
        Returns:
            bool: İşlem başarısı
        """
        # Sabit cüzdan dosyası yolu
        WALLET_FILE = WALLET_DATA_FILE
        
        logger.info(f"Cüzdanlar '{WALLET_FILE}' dosyasına kaydediliyor...")
        
        try:
            wallet_data = []
            for wallet in self.wallets:
                if "keypair" not in wallet:
                    logger.warning(f"UYARI: Geçersiz cüzdan formatı, keypair eksik")
                    continue
                    
                keypair = wallet["keypair"]
                # Keypair'den secret'ı (seed) al
                wallet_data.append({
                    "pubkey": str(keypair.pubkey()),
                    "private_key": base58.b58encode(keypair.secret()).decode('utf-8'),
                    "connected": wallet.get("connected", True)
                })
            
            # Klasörü oluştur
            os.makedirs(os.path.dirname(WALLET_FILE), exist_ok=True)
            
            with open(WALLET_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    "wallets": wallet_data,
                    "active_wallet_index": self.active_wallet_index
                }, f, indent=2)
            logger.info(f"✅ {len(wallet_data)} cüzdan kaydedildi.")
            return True
        except Exception as e:
            logger.error(f"❌ Cüzdan kaydedilemedi: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def load_wallets(self):
        """
        Cüzdan bilgilerini ayrı bir dosyadan yükle
        
        Returns:
            bool: İşlem başarısı
        """
        # Sabit cüzdan dosyası yolu
        WALLET_FILE = WALLET_DATA_FILE
        
        logger.info(f"Cüzdanlar '{WALLET_FILE}' dosyasından yükleniyor...")
        
        try:
            if not os.path.exists(WALLET_FILE):
                logger.warning(f"⚠️ Cüzdan dosyası bulunamadı: {WALLET_FILE}")
                return False
                
            with open(WALLET_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.wallets = []
            self.active_wallet_index = -1
            
            for wallet_data in data.get("wallets", []):
                try:
                    if "private_key" not in wallet_data:
                        logger.warning(f"UYARI: Cüzdan verisinde private_key eksik")
                        continue
                        
                    seed_bytes = base58.b58decode(wallet_data["private_key"])
                    # from_bytes yerine from_seed kullan ve sadece ilk 32 byte'ı al
                    keypair = Keypair.from_seed(seed_bytes[:32])
                    pubkey = str(keypair.pubkey())
                    
                    # Kayıttaki pubkey ile oluşturulan pubkey'i karşılaştır
                    if "pubkey" in wallet_data and wallet_data["pubkey"] != pubkey:
                        logger.warning(f"UYARI: Pubkey uyuşmazlığı: {wallet_data['pubkey']} != {pubkey}")
                    
                    self.wallets.append({
                        "keypair": keypair,
                        "connected": wallet_data.get("connected", True)
                    })
                    logger.info(f"Cüzdan yüklendi: {pubkey}")
                except Exception as e:
                    logger.error(f"Cüzdan yükleme hatası: {e}")
                    import traceback
                    traceback.print_exc()
            
            if self.wallets:
                active_index = data.get("active_wallet_index", 0)
                if 0 <= active_index < len(self.wallets):
                    self.active_wallet_index = active_index
                    
                    # Aktif cüzdan bilgilerini de ayarla
                    self.wallet_address = self.wallets[active_index]['keypair'].pubkey()
                    self.keypair = self.wallets[active_index]['keypair']
                    
                    logger.info(f"Aktif cüzdan ayarlandı: {self.wallets[active_index]['keypair'].pubkey()}")
                else:
                    self.active_wallet_index = 0
                    
                    # Aktif cüzdan bilgilerini ilk cüzdanla ayarla
                    self.wallet_address = self.wallets[0]['keypair'].pubkey()
                    self.keypair = self.wallets[0]['keypair']
                    
                    logger.warning(f"Geçersiz aktif_cüzdan_indeksi ({active_index}), 0 olarak ayarlandı")
            else:
                logger.warning("Hiç cüzdan yüklenemedi.")
                
            logger.info(f"✅ Toplam {len(self.wallets)} cüzdan yüklendi, aktif indeks: {self.active_wallet_index}")
            return True
        except Exception as e:
            logger.error(f"❌ Cüzdan yükleme hatası: {e}")
            import traceback
            traceback.print_exc()
            return False

    def load_wallet_data(self):
        """
        Config'deki dosya yolunu kullanarak cüzdan verilerini yükler
        """
        try:
            with open(WALLET_DATA_FILE, 'r') as f:
                data = json.load(f)
                active_index = data.get("active_wallet_index", 0)
                wallet = data["wallets"][active_index]
                self.wallet_address = Pubkey.from_string(wallet["pubkey"])
                self.keypair = Keypair.from_base58_string(wallet["private_key"])
                logger.info(f"Aktif cüzdan yüklendi: {self.wallet_address}")
        except Exception as e:
            logger.error(f"Cüzdan yükleme hatası: {e}")
            raise

    async def get_sol_balance(self):
        """
        Cüzdandaki SOL bakiyesini getirir
        
        Returns:
            float: SOL bakiyesi
        """
        try:
            response = await self.rpc_client.get_balance(self.wallet_address)
            balance = response.value / 1_000_000_000  # Lamports to SOL
            logger.debug(f"SOL bakiyesi: {balance}")
            return balance
        except Exception as e:
            logger.error(f"SOL bakiye hatası: {e}")
            return 0

    async def get_token_balance(self, token_mint: str):
        """
        Belirli bir token'ın bakiyesini getirir
        
        Args:
            token_mint (str): Token mint adresi
        
        Returns:
            float: Token bakiyesi
        """
        try:
            token_mint_pubkey = Pubkey.from_string(token_mint)
            token_account = get_associated_token_address(self.wallet_address, token_mint_pubkey)
            response = await self.rpc_client.get_token_account_balance(token_account)
            if response.value is None:
                logger.debug(f"Token hesabı yok: {token_mint}")
                return 0
            balance = response.value.ui_amount
            logger.debug(f"Token bakiyesi: {token_mint}, {balance}")
            return balance
        except Exception as e:
            logger.debug(f"Token bakiye hatası: {e}")
            return 0

    async def ensure_token_account(self, token_mint: str):
        """
        Token hesabını kontrol eder, yoksa oluşturur
        
        Args:
            token_mint (str): Token mint adresi
        
        Returns:
            Pubkey: Associated token hesap adresi
        """
        try:
            token_mint_pubkey = Pubkey.from_string(token_mint)
            token_account = get_associated_token_address(self.wallet_address, token_mint_pubkey)
            account_info = await self.rpc_client.get_account_info(token_account)
            if account_info.value is None:
                tx = Transaction()
                tx.add(create_associated_token_account(
                    payer=self.wallet_address,
                    owner=self.wallet_address,
                    mint=token_mint_pubkey
                ))
                response = await self.rpc_client.send_transaction(tx, self.keypair)
                logger.info(f"Token hesabı oluşturuldu: {token_mint}, TX: {response.value}")
            return token_account
        except Exception as e:
            logger.error(f"Token hesabı oluşturma hatası: {e}")
            raise

    async def buy_token(self, mint_address, amount):
        """
        Belirli bir token için SOL ile alım yapar
        
        Args:
            mint_address (str): Alınacak tokenın mint adresi
            amount (float): Alım miktarı (SOL)
            
        Returns:
            str: İşlem hash'i
        """
        from gotnw_tradebot.network.api_client import execute_swap
        return await execute_swap(self, mint_address, amount, buy=True)

    async def sell_token(self, mint_address, amount):
        """
        Belirli bir tokenden SOL'a swap yapar
        
        Args:
            mint_address (str): Satılacak tokenın mint adresi
            amount (float): Satış miktarı
            
        Returns:
            str: İşlem hash'i
        """
        from gotnw_tradebot.network.api_client import execute_swap
        return await execute_swap(self, mint_address, amount, buy=False)

    async def get_enhanced_transaction_details(self, transaction_signatures):
        """
        Helius Enhanced API ile detaylı işlem bilgilerini alır
        
        Args:
            transaction_signatures (list): İşlem imzaları
            
        Returns:
            list: İşlem detayları
        """
        url = "https://api.helius.xyz/v0/transactions/"
        api_key = "92cbc54b-c8e5-4de4-ac41-a4fcffc600e4"
        
        try:
            async with aiohttp.ClientSession() as session:
                params = {"api-key": api_key}
                payload = {
                    "transactions": transaction_signatures,
                    "options": {
                        "showNativeTransfers": True,
                        "showTokenTransfers": True,
                        "parseInstructions": True
                    }
                }
                
                async with session.post(url, params=params, json=payload) as response:
                    if response.status == 200:
                        transaction_details = await response.json()
                        return self._parse_enhanced_transactions(transaction_details)
                    else:
                        log_to_file(f"İşlem detay çekme hatası: {response.status}")
                        return []
        
        except Exception as e:
            log_to_file(f"Gelişmiş işlem detay hatası: {e}")
            return []

    def _parse_enhanced_transactions(self, transactions):
        """
        Gelişmiş işlem detaylarını yorumlar
        
        Args:
            transactions (list): Ham işlem verileri
            
        Returns:
            list: İşlenmiş işlem verileri
        """
        parsed_transactions = []
        for tx in transactions:
            parsed_tx = {
                "signature": tx.get("signature"),
                "timestamp": tx.get("timestamp"),
                "fee": tx.get("fee"),
                "status": tx.get("status"),
                "native_transfers": [],
                "token_transfers": [],
                "instructions": []
            }
            
            # Native transferları ekle
            if tx.get("nativeTransfers"):
                for transfer in tx["nativeTransfers"]:
                    parsed_tx["native_transfers"].append({
                        "from": transfer.get("fromUserAccount"),
                        "to": transfer.get("toUserAccount"),
                        "amount": transfer.get("amount")
                    })
            
            # Token transferlarını ekle
            if tx.get("tokenTransfers"):
                for transfer in tx["tokenTransfers"]:
                    parsed_tx["token_transfers"].append({
                        "from": transfer.get("fromUserAccount"),
                        "to": transfer.get("toUserAccount"),
                        "token_address": transfer.get("mint"),
                        "amount": transfer.get("amount")
                    })
            
            # İşlem talimatlarını ekle
            if tx.get("instructions"):
                for instruction in tx["instructions"]:
                    parsed_tx["instructions"].append({
                        "program": instruction.get("programId"),
                        "type": instruction.get("type"),
                        "data": instruction.get("data")
                    })
            
            parsed_transactions.append(parsed_tx)
        
        return parsed_transactions

    async def get_token_metadata(self, token_addresses):
        """
        Helius API ile token meta verilerini çeker
        
        Args:
            token_addresses (list): Token adresleri
            
        Returns:
            list: Token meta verileri
        """
        url = "https://api.helius.xyz/v0/tokens/metadata"
        api_key = "92cbc54b-c8e5-4de4-ac41-a4fcffc600e4"
        
        try:
            async with aiohttp.ClientSession() as session:
                params = {"api-key": api_key}
                payload = {"mintAccounts": token_addresses}
                
                async with session.post(url, params=params, json=payload) as response:
                    if response.status == 200:
                        token_metadata = await response.json()
                        return token_metadata
                    else:
                        log_to_file(f"Token metadata çekme hatası: {response.status}")
                        return []
        
        except Exception as e:
            log_to_file(f"Token metadata hatası: {e}")
            return []

# Global instance
wallet_manager = WalletManager()

# Yardımcı fonksiyonlar
async def get_available_balance():
    """
    Kullanılabilir bakiyeyi hesaplar
    
    Returns:
        float: Kullanılabilir bakiye
    """
    from gotnw_tradebot.utils.trade_utils import is_night_mode
    balance = await wallet_manager.get_balance()
    if is_night_mode():
        return balance * (trade_settings.get("night_mode_limit", 30) / 100)  # Gece modunda bakiyenin belirtilen yüzdesini kullan
    return balance


async def async_input(prompt):
    """
    Asenkron olarak kullanıcıdan girdi alır
    
    Args:
        prompt (str): Gösterilecek mesaj
        
    Returns:
        str: Kullanıcı girdisi
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, input, prompt)
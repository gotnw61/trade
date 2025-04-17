# -*- coding: utf-8 -*-
"""
GOTNW TradeBot
--------------
Solana blockchain üzerinde token işlemleri için otomatik alım/satım botu.
"""

__version__ = "1.0.0"
__author__ = "GOTNW TradeBot"
__license__ = "MIT"
__description__ = "Solana token işlemleri için otomatik alım/satım botu"

# Modülleri dışa aktar
from core import TradeBot
from wallet import wallet_manager, get_available_balance
from analysis import EnhancedTokenAnalyzer, TokenAnalyzer
from utils import log_to_file, animated_text, format_price

# Ana fonksiyonlar
from main import save_state, load_state, start_application
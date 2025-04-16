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
from gotnw_tradebot.core import TradeBot
from gotnw_tradebot.wallet import wallet_manager, get_available_balance
from gotnw_tradebot.analysis import EnhancedTokenAnalyzer, TokenAnalyzer
from gotnw_tradebot.utils import log_to_file, animated_text, format_price

# Ana fonksiyonlar
from gotnw_tradebot.main import save_state, load_state, start_application
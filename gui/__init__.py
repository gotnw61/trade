# -*- coding: utf-8 -*-
"""
GOTNW TradeBot GUI modülleri
"""

# Ana GUI bileşenleri
from gui.main_window import start_gui, TradeBotGUI
from gui.dashboard import create_dashboard
from gui.trades_panel import create_trades_panel
from gui.wallet_panel import create_wallet_panel
from gui.settings_panel import create_settings_panel
from gui.ai_panel import create_ai_panel

# Versiyonlama
__version__ = "1.0.0"
__author__ = "GOTNW TradeBot"
__description__ = "Solana token işlem botu için grafik arayüz modülleri"

__all__ = [
    'start_gui',
    'TradeBotGUI',
    'create_dashboard',
    'create_trades_panel',
    'create_wallet_panel',
    'create_settings_panel',
    'create_ai_panel'
]
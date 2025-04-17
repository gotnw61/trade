# -*- coding: utf-8 -*-
import os
import platform
import sys

# Uygulama kök dizinini belirle
if getattr(sys, 'frozen', False):  # PyInstaller ile paketlenmiş uygulamalar için
    APP_ROOT = os.path.dirname(sys.executable)
else:
    APP_ROOT = os.path.dirname(os.path.abspath(__file__))

# Masaüstü yolunu belirle
if platform.system() == 'Windows':
    DESKTOP_PATH = os.path.join(os.path.expanduser('~'), 'Desktop')
else:
    DESKTOP_PATH = os.path.join(os.path.expanduser('~'), 'Desktop')

# Sabit yollar ve ayarlar
LOG_PATH = os.path.join(APP_ROOT, "logs")

# Doğrudan belirtilen sabit yollar
INPUT_FILE = r"C:\Users\Lenovo\OneDrive\Desktop\filtered_messages.json"
STATE_FILE = r"C:\Users\Lenovo\OneDrive\Desktop\tradebot\tradebot_state.json"

DAILY_REPORT_FILE = os.path.join(APP_ROOT, "daily_report.txt")
AI_MODEL_FILE = os.path.join(APP_ROOT, "models", "pump_prediction_model.pkl")

# Klasörleri oluştur
os.makedirs(LOG_PATH, exist_ok=True)
os.makedirs(os.path.join(APP_ROOT, "models"), exist_ok=True)

EMAIL_ADDRESS = "coskunresul19@gmail.com"
EMAIL_PASSWORD = "agcg nrqa jqdz ervc"
RECEIVER_EMAIL = "resulcskn0@gmail.com"

# Debug modu
DEBUG_MODE = False  # Varsayılan olarak False

# Ticaret ayarları
trade_settings = {
    "autobuy_enabled": True,
    "autosell_enabled": True,
    "buy_amount_sol": 0.2,
    "sell_profit_targets": [
        {"profit": 20, "sell_percentage": 25},
        {"profit": 50, "sell_percentage": 25},
        {"profit": 100, "sell_percentage": 25},
        {"profit": 150, "sell_percentage": 100}
    ],
    "sell_stop_loss_levels": [
        {"loss": -5, "sell_percentage": 50},
        {"loss": -10, "sell_percentage": 100}
    ],
    "slippage_tolerance": 1,
    "trailing_stop_loss": 5.0,
    "max_positions": 5,
    "max_investment_percentage": 50.0,
    "min_liquidity_usd": 5000,
    "max_portfolio_loss": 30,
    "simulation_mode": True,
    "simulation_balance": 1000.0,
    "sound_notifications": True,
    "price_alerts": {},
    "auto_slippage_adjust": True,
    "min_balance_sol": 0.005,
    "night_mode_enabled": False,
    "night_mode_start": "00:00",
    "night_mode_end": "08:00",
    "night_mode_limit": 30,
    "sniping_enabled": False,
    "sniping_max_percentage": 20,
    "gas_fee_optimization": True,
    "dump_detection_percentage": 60,
    "dump_time_window": 5,
    "candle_interval": 1,
    "fast_buy_threshold": 0.00001000,
    "rapid_cycle_enabled": True,
    "rapid_cycle_interval": 0.5,
    "momentum_enabled": True,
    "momentum_threshold": 5.0,
    "momentum_window": 5,
    "whale_tracking_enabled": True,
    "whale_threshold_sol": 5.0,
    "volatility_trading_enabled": True,
    "volatility_threshold": 8.0,
    "liquidity_exit_enabled": True,
    "liquidity_exit_threshold": 25.0,
    "whale_dump_detection_enabled": True,
    "whale_dump_threshold": 10.0,
    "price_deviation_enabled": True,
    "price_deviation_threshold": 3.0,
    "token_diversification_enabled": True,
    "max_token_category": 3,
    "dip_buy_enabled": True,
    "dip_buy_threshold": 15.0,
    "volume_drop_detection_enabled": True,
    "volume_drop_threshold": 40.0,
    "ai_enabled": True,
    "ai_confidence_threshold": 0.7,
    "micro_pump_detection_enabled": True,
    "micro_pump_threshold": 3.0,
    "micro_pump_interval": 30,
    "ai_pump_duration_prediction_enabled": True,
    "min_pump_duration_seconds": 60,
    "max_positions_per_category": 2
}

# Strateji profilleri
STRATEGY_PROFILES = {
    "agresif": {
        "sell_profit_targets": [{"profit": 20, "sell_percentage": 30}, {"profit": 50, "sell_percentage": 70},
                                {"profit": 100, "sell_percentage": 100}],
        "sell_stop_loss_levels": [{"loss": -5, "sell_percentage": 50}, {"loss": -10, "sell_percentage": 100}],
        "trailing_stop_loss": 3.0,
        "momentum_threshold": 3.0,
        "dip_buy_threshold": 10.0,
        "micro_pump_threshold": 2.0
    },
    "dengeli": {
        "sell_profit_targets": [{"profit": 10, "sell_percentage": 33}, {"profit": 20, "sell_percentage": 33},
                                {"profit": 50, "sell_percentage": 34}],
        "sell_stop_loss_levels": [{"loss": -10, "sell_percentage": 50}, {"loss": -20, "sell_percentage": 100}],
        "trailing_stop_loss": 5.0,
        "momentum_threshold": 5.0,
        "dip_buy_threshold": 15.0,
        "micro_pump_threshold": 3.0
    },
    "muhafazakar": {
        "sell_profit_targets": [{"profit": 5, "sell_percentage": 50}, {"profit": 10, "sell_percentage": 50}],
        "sell_stop_loss_levels": [{"loss": -15, "sell_percentage": 50}, {"loss": -25, "sell_percentage": 100}],
        "trailing_stop_loss": 7.0,
        "momentum_threshold": 8.0,
        "dip_buy_threshold": 20.0,
        "micro_pump_threshold": 5.0
    }
}

STRATEGIES = STRATEGY_PROFILES

current_strategy = "dengeli"

# Global değişkenler
open_windows = {}  # Dictionary olarak tanımlama

last_action_message = "Program başlatıldı"

# Helius WebSocket
HELIUS_WS_URL = "wss://mainnet.helius-rpc.com/?api-key=92cbc54b-c8e5-4de4-ac41-a4fcffc600e4"
# Solana RPC
SOLANA_RPC_URL = "https://api.mainnet-beta.solana.com"
# Cüzdan
WALLET_DATA_FILE = r"C:\Users\Lenovo\OneDrive\Desktop\tradebot\wallet_data.json"
# Alım/satım
AUTO_BUY_ENABLED = True
MIN_LIQUIDITY_SOL = 10
MAX_BUY_AMOUNT_SOL = 0.1
MAX_SELL_AMOUNT_TOKEN = 1000000
PROFIT_TARGET_PERCENT = 10.0
STOP_LOSS_PERCENT = -5.0
MIN_PRICE_MOVEMENT = 0.5
SLIPPAGE_BPS = 50  # %0.5 slippage
# Raydium
RAYDIUM_PROGRAM_ID = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
RAYDIUM_AUTHORITY = "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
SERUM_PROGRAM_ID = "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"
# Genel
SIMULATION_MODE = True  # Gerçek mainnet
PRICE_UPDATE_INTERVAL = 0.1
MAX_RETRIES = 3
MIN_SOL_BALANCE = 0.05  # Minimum cüzdan SOL bakiyesi
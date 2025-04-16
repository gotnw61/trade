# -*- coding: utf-8 -*-

def format_price(price):
    """
    Formats price with appropriate decimal places.
    
    Args:
        price (float): Price to be formatted
    
    Returns:
        str: Formatted price string
    """
    if not isinstance(price, (int, float)) or price <= 0:
        return "Bilinmeyen"
    if price < 0.001:
        return f"{price:.10f}".rstrip('0').rstrip('.')
    return f"{price:.8f}"

def print_wallet_info(wallet, balance, sol_price):
    """
    Konsola cüzdan bilgilerini yazdırır
    
    Args:
        wallet (str): Cüzdan adresi
        balance (float): SOL bakiye
        sol_price (float): SOL/USD fiyatı
    """
    from gotnw_tradebot.utils.console_utils import clear_screen
    
    clear_screen()
    print(f"\033[36m===== GOTNW TradeBot Cüzdan Bilgileri =====\033[0m")
    print(f"\033[32mCüzdan Adresi:\033[0m {wallet}")
    print(f"\033[32mSOL Bakiye:\033[0m {balance:.4f}")
    print(f"\033[32mSOL/USD Fiyatı:\033[0m ${sol_price:.2f}")
    print(f"\033[32mToplam Değer:\033[0m ${balance * sol_price:.2f}")
    print(f"\033[36m==========================================\033[0m")
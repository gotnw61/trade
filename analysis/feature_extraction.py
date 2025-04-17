# -*- coding: utf-8 -*-
"""
Özellik çıkarma fonksiyonları
"""

import numpy as np
from datetime import datetime, timedelta

def extract_features(analyzer, mint_address, window_sizes=[5, 10, 20, 50, 100]):
    """Bir token için çeşitli pencere boyutlarında kapsamlı öznitelikler çıkarır"""
    features = {}

    # Fiyat tarihi yoksa veya çok azsa, boş öznitelikler döndür
    if mint_address not in analyzer.price_history or len(analyzer.price_history[mint_address]) < max(window_sizes):
        return features

    # Temel fiyat verisi
    prices = [item["price"] for item in analyzer.price_history[mint_address]]
    
    # Veri tipi kontrolü
    if not all(isinstance(p, (int, float)) for p in prices):
        analyzer.update_log(mint_address, f"❌ Fiyat listesinde geçersiz değerler var")
        prices = [p for p in prices if isinstance(p, (int, float))]
        if not prices:
            return features
    
    current_price = prices[-1]
    features["current_price"] = current_price

    # Fiyat varyansı
    features["price_variance"] = np.var(prices) if len(prices) > 1 else 0

    # Güvenli Skewness ve Kurtosis hesaplamaları
    def safe_skew(data):
        if len(set(data)) <= 1:  # Tüm veriler aynıysa
            return 0.0
        from scipy.stats import skew
        return skew(data)

    def safe_kurtosis(data):
        if len(set(data)) <= 1:  # Tüm veriler aynıysa
            return 0.0
        from scipy.stats import kurtosis
        return kurtosis(data)

    try:
        if len(prices) > 2:
            features["price_skewness"] = safe_skew(prices)
            features["price_kurtosis"] = safe_kurtosis(prices)
        else:
            features["price_skewness"] = 0.0
            features["price_kurtosis"] = 0.0
    except Exception as e:
        features["price_skewness"] = 0.0
        features["price_kurtosis"] = 0.0
        analyzer.update_log(mint_address, f"Özellik çıkarımında hata: {e}")

    # Hacim verisi
    if mint_address in analyzer.volume_history and len(analyzer.volume_history[mint_address]) > 0:
        volumes = [item["volume"] for item in analyzer.volume_history[mint_address]]
        if not all(isinstance(v, (int, float)) for v in volumes):
            volumes = [v for v in volumes if isinstance(v, (int, float))]
            if not volumes:
                features["current_volume"] = 0
                return features
                
        features["current_volume"] = volumes[-1]
        features["volume_price_ratio"] = volumes[-1] / (current_price + 0.0000001)
        if len(volumes) > 5:
            volume_trend = (sum(volumes[-3:]) / 3) / (sum(volumes[-6:-3]) / 3 + 0.0000001)
            features["volume_trend"] = volume_trend
    else:
        features["current_volume"] = 0

    # Likidite verisi
    if mint_address in analyzer.liquidity_history and len(analyzer.liquidity_history[mint_address]) > 0:
        liquidities = [item["liquidity"] for item in analyzer.liquidity_history[mint_address]]
        if not all(isinstance(l, (int, float)) for l in liquidities):
            liquidities = [l for l in liquidities if isinstance(l, (int, float))]
            if not liquidities:
                features["current_liquidity"] = 0
                return features
                
        features["current_liquidity"] = liquidities[-1]
    else:
        features["current_liquidity"] = 0

    # Farklı pencere boyutları için öznitelikler
    for window in window_sizes:
        if len(prices) < window:
            continue

        window_prices = prices[-window:]
        if window_prices[0] > 0:
            price_change_pct = ((window_prices[-1] - window_prices[0]) / window_prices[0]) * 100
        else:
            price_change_pct = 0
        features[f"price_change_{window}"] = price_change_pct

        features[f"price_mean_{window}"] = np.mean(window_prices)
        features[f"price_std_{window}"] = np.std(window_prices)
        features[f"price_min_{window}"] = np.min(window_prices)
        features[f"price_max_{window}"] = np.max(window_prices)

        price_changes = np.diff(window_prices)
        if len(price_changes) > 0:
            gains = np.array([max(0, change) for change in price_changes])
            losses = np.array([max(0, -change) for change in price_changes])
            avg_gain = np.mean(gains) if np.sum(gains) > 0 else 0.0001
            avg_loss = np.mean(losses) if np.sum(losses) > 0 else 0.0001
            rsi = 100 - (100 / (1 + (avg_gain / max(avg_loss, 0.0001))))
            features[f"rsi_{window}"] = rsi

        if len(window_prices) > 1:
            log_returns = np.diff(np.log(np.array(window_prices) + 0.0001))
            features[f"volatility_{window}"] = np.std(log_returns) * 100

        if len(window_prices) >= 2:
            momentum = window_prices[-1] - window_prices[0]
            features[f"momentum_{window}"] = momentum

        if mint_address in analyzer.volume_history and len(analyzer.volume_history[mint_address]) >= window:
            window_volumes = [item["volume"] for item in analyzer.volume_history[mint_address][-window:]]
            if not all(isinstance(v, (int, float)) for v in window_volumes):
                window_volumes = [v for v in window_volumes if isinstance(v, (int, float))]
                if not window_volumes:
                    continue
                    
            features[f"volume_mean_{window}"] = np.mean(window_volumes)
            features[f"volume_std_{window}"] = np.std(window_volumes)
            features[f"volume_change_{window}"] = ((window_volumes[-1] - window_volumes[0]) / (window_volumes[0] + 0.0001)) * 100

        if mint_address in analyzer.liquidity_history and len(analyzer.liquidity_history[mint_address]) >= window:
            window_liquidity = [item["liquidity"] for item in analyzer.liquidity_history[mint_address][-window:]]
            if not all(isinstance(l, (int, float)) for l in window_liquidity):
                window_liquidity = [l for l in window_liquidity if isinstance(l, (int, float))]
                if not window_liquidity:
                    continue
                    
            features[f"liquidity_mean_{window}"] = np.mean(window_liquidity)
            features[f"liquidity_std_{window}"] = np.std(window_liquidity)
            features[f"liquidity_change_{window}"] = ((window_liquidity[-1] - window_liquidity[0]) / (window_liquidity[0] + 0.0001)) * 100

        if hasattr(analyzer, 'transaction_history') and mint_address in analyzer.transaction_history:
            now = datetime.now()
            window_minutes = timedelta(minutes=window)
            recent_transactions = [tx for tx in analyzer.transaction_history[mint_address]
                                if now - tx["timestamp"] <= window_minutes]
            buy_count = sum(1 for tx in recent_transactions if tx["type"] == "buy")
            sell_count = sum(1 for tx in recent_transactions if tx["type"] == "sell")
            buy_volume = sum(tx["amount"] for tx in recent_transactions if tx["type"] == "buy")
            sell_volume = sum(tx["amount"] for tx in recent_transactions if tx["type"] == "sell")
            features[f"buy_count_{window}"] = buy_count
            features[f"sell_count_{window}"] = sell_count
            features[f"buy_volume_{window}"] = buy_volume
            features[f"sell_volume_{window}"] = sell_volume
            features[f"volume_ratio_{window}"] = buy_volume / (sell_volume + 0.0001)
            features[f"transaction_count_{window}"] = len(recent_transactions)

    if hasattr(analyzer, 'whale_transactions') and mint_address in analyzer.whale_transactions:
        whale_threshold = analyzer.config.get("whale_threshold_sol", 10) if hasattr(analyzer, 'config') else 10
        whale_transactions = [tx for tx in analyzer.whale_transactions[mint_address]
                            if tx["amount_sol"] >= whale_threshold]
        recent_whale_txs = [tx for tx in whale_transactions
                          if datetime.now() - tx["timestamp"] <= timedelta(hours=24)]
        features["whale_tx_count_24h"] = len(recent_whale_txs)
        features["whale_buy_count_24h"] = sum(1 for tx in recent_whale_txs if tx["type"] == "buy")
        features["whale_sell_count_24h"] = sum(1 for tx in recent_whale_txs if tx["type"] == "sell")
        features["whale_buy_volume_24h"] = sum(tx["amount_sol"] for tx in recent_whale_txs if tx["type"] == "buy")
        features["whale_sell_volume_24h"] = sum(tx["amount_sol"] for tx in recent_whale_txs if tx["type"] == "sell")

    current_time = datetime.now()
    features["hour_of_day"] = current_time.hour
    features["day_of_week"] = current_time.weekday()
    features["is_weekend"] = 1 if current_time.weekday() >= 5 else 0

    if len(window_sizes) >= 2 and len(prices) > max(window_sizes):
        short_window = min(window_sizes)
        long_window = max(window_sizes)
        short_momentum = analyzer.calculate_momentum(mint_address, window=short_window)
        long_momentum = analyzer.calculate_momentum(mint_address, window=long_window)
        features["momentum_acceleration"] = short_momentum - long_momentum

    for window in window_sizes:
        if len(prices) < window:
            continue
        window_prices = prices[-window:]
        direction_changes = 0
        for i in range(2, len(window_prices)):
            if (window_prices[i] > window_prices[i-1] and window_prices[i-1] < window_prices[i-2]) or \
               (window_prices[i] < window_prices[i-1] and window_prices[i-1] > window_prices[i-2]):
                direction_changes += 1
        features[f"zigzag_{window}"] = direction_changes / (window - 2) if window > 2 else 0

        flat_regions = 0
        for i in range(1, len(window_prices)):
            if abs(window_prices[i] - window_prices[i-1]) / (window_prices[i-1] + 0.0000001) < 0.0001:
                flat_regions += 1
        features[f"flat_regions_{window}"] = flat_regions / (window - 1)

    return features
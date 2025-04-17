# -*- coding: utf-8 -*-
"""
Fiyat deseni tespit fonksiyonları
"""

import numpy as np
from datetime import datetime


def detect_dip(analyzer, mint_address, current_price, window=20, advanced_analysis=True):
    """Gelişmiş ve çok katmanlı dip fiyatı tespiti."""
    # Tüm girdi parametrelerinin tiplerini kontrol et
    if not isinstance(current_price, (int, float)):
        analyzer.update_log(mint_address, f"Hata: current_price beklenmeyen tipte: {type(current_price)}")
        return {
            "is_dip": False,
            "dip_type": None,
            "metrics": {
                "dip_percentage": 0,
                "dip_depth": 0,
                "confidence": 0,
                "recovery_potential": 0,
            },
            "technical_indicators": {},
            "risk_assessment": {},
        }

    if mint_address not in analyzer.price_history or len(analyzer.price_history[mint_address]) < window:
        return {
            "is_dip": False,
            "dip_type": None,
            "metrics": {
                "dip_percentage": 0,
                "dip_depth": 0,
                "confidence": 0,
                "recovery_potential": 0,
            },
            "technical_indicators": {},
            "risk_assessment": {},
        }
    
    # Fiyat ve hacim geçmişini al
    prices = [item["price"] for item in analyzer.price_history[mint_address][-window:]]
    
    # Temel kontroller
    if not prices or min(prices) <= 0:
        return {
            "is_dip": False,
            "dip_type": None,
            "metrics": {
                "dip_percentage": 0,
                "dip_depth": 0,
                "confidence": 0,
                "recovery_potential": 0,
            },
            "technical_indicators": {},
            "risk_assessment": {},
        }
    
    # Fiyat istatistikleri
    max_price = max(prices)
    min_price = min(prices)
    median_price = sorted(prices)[len(prices) // 2]
    
    # Dip yüzdesi ve derinliği
    dip_percentage = ((max_price - current_price) / max_price) * 100
    dip_depth = max_price - current_price
    
    # Gelişmiş dip tespiti
    def advanced_dip_classification():
        """Çoklu dip deseni analizi."""
        dip_stages = []
        for i in range(1, len(prices)):
            stage_drop = ((prices[i - 1] - prices[i]) / prices[i - 1]) * 100
            if stage_drop > 3:  # %3'ten fazla düşüş
                dip_stages.append(stage_drop)
        
        # Dip desenlerinin sınıflandırılması
        if len(dip_stages) >= 3:
            return "cascading_dip"
        elif len(dip_stages) == 2:
            return "stepped_dip"
        elif len(dip_stages) == 1:
            return "sharp_dip"
        return "gradual_dip"
    
    # Teknik göstergeler
    def calculate_technical_indicators():
        """Önemli teknik göstergeleri hesaplar."""
        def calculate_rsi(data, periods=14):
            import pandas as pd
            delta = np.diff(data)
            gains = delta.clip(min=0)
            losses = -delta.clip(max=0)
            
            avg_gain = pd.Series(gains).rolling(window=periods).mean()
            avg_loss = pd.Series(losses).rolling(window=periods).mean()
            
            relative_strength = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + relative_strength))
            return rsi.iloc[-1] if not rsi.empty else 50
        
        return {
            "rsi": calculate_rsi(prices),
            "bollinger_band_width": np.std(prices) / np.mean(prices) * 100,
            "price_momentum": prices[-1] - prices[0],
            "volatility": np.std(prices) * 100,
        }
    
    # Hacim analizi
    def volume_analysis():
        """Hacim düşüşünü analiz eder."""
        if mint_address in analyzer.volume_history and len(analyzer.volume_history[mint_address]) >= window:
            volumes = [item["volume"] for item in analyzer.volume_history[mint_address][-window:]]
            volume_drop = ((max(volumes) - volumes[-1]) / max(volumes)) * 100
            return volume_drop
        return 0
    
    # Risk değerlendirmesi
    def assess_recovery_risk():
        """Fiyat hareketlerine göre risk değerlendirir."""
        recent_prices = prices[-3:]
        price_trend = np.polyfit(range(len(recent_prices)), recent_prices, 1)[0]
        
        volatility = np.std(prices) * 100
        momentum = prices[-1] - prices[0]
        
        max_abs_price = max(abs(p) for p in prices if isinstance(p, (int, float)))
        
        risk_score = (
            (1 if price_trend > 0 else -1) *
            (1 + abs(momentum) / max(max_abs_price, 0.0001)) *
            (1 / (1 + volatility))
        )
        
        return {
            "price_trend": "rising" if price_trend > 0 else "falling",
            "momentum_strength": abs(momentum) if isinstance(momentum, (int, float)) else 0,
            "recovery_potential": max(0, min(1, risk_score + 0.5)),
        }
    
    # Dip sınıflandırması
    def classify_dip():
        """Çoklu kritere göre dip tespiti."""
        criteria_met = 0
        
        # Dip yüzdesi kriterleri
        if 15 <= dip_percentage < 25:
            criteria_met += 1
        elif 25 <= dip_percentage < 40:
            criteria_met += 2
        elif dip_percentage >= 40:
            criteria_met += 3
        
        # Hacim düşüşü
        volume_drop = volume_analysis()
        if volume_drop > 30:
            criteria_met += 1
        
        # Teknik göstergeler
        if advanced_analysis:
            tech_indicators = calculate_technical_indicators()
            if tech_indicators["rsi"] < 30:  # Aşırı satılmış
                criteria_met += 1
            if tech_indicators["bollinger_band_width"] > 10:  # Yüksek volatilite
                criteria_met += 1
        
        return criteria_met
    
    # Nihai dip tespiti
    dip_classification = classify_dip()
    
    # Config ayarlarını güvenli şekilde al
    dip_buy_threshold = analyzer.config.get("dip_buy_threshold", 15.0) if hasattr(analyzer, "config") else 15.0
    
    # Son analiz
    is_dip = dip_percentage >= dip_buy_threshold and dip_classification >= 2
    
    # Sonuç döndürme
    result = {
        "is_dip": is_dip,
        "dip_type": advanced_dip_classification() if is_dip else None,
        "metrics": {
            "dip_percentage": dip_percentage,
            "dip_depth": dip_depth,
            "confidence": min(1.0, dip_classification / 5),
            "recovery_potential": assess_recovery_risk()["recovery_potential"],
        },
        "technical_indicators": calculate_technical_indicators() if advanced_analysis else {},
        "risk_assessment": assess_recovery_risk(),
    }
    
    return result


def detect_pump_pattern(analyzer, mint_address, window=20):
    """Özel pump desenlerini tespit eder."""
    if mint_address not in analyzer.price_history or len(analyzer.price_history[mint_address]) < window:
        return {
            "is_pump": False,
            "pattern_type": None,
            "confidence": 0,
            "details": {},
        }

    prices = [item["price"] for item in analyzer.price_history[mint_address][-window:]]
    volumes = (
        [item["volume"] for item in analyzer.volume_history[mint_address][-window:]]
        if mint_address in analyzer.volume_history and len(analyzer.volume_history[mint_address]) >= window
        else []
    )

    # Veri tipi kontrolü
    if not all(isinstance(p, (int, float)) for p in prices):
        prices = [p for p in prices if isinstance(p, (int, float))]
        if not prices:
            return {
                "is_pump": False,
                "pattern_type": None,
                "confidence": 0,
                "details": {},
            }
            
    if volumes and not all(isinstance(v, (int, float)) for v in volumes):
        volumes = [v for v in volumes if isinstance(v, (int, float))]

    result = {
        "is_pump": False,
        "pattern_type": None,
        "confidence": 0,
        "details": {},
    }

    if len(prices) > 5 and len(volumes) > 5:
        price_change = ((prices[-1] - prices[-6]) / prices[-6]) * 100 if prices[-6] > 0 else 0
        volume_change = ((volumes[-1] - volumes[-6]) / volumes[-6]) * 100 if volumes[-6] > 0 else 0
        if price_change > 15 and volume_change > 50:
            result["is_pump"] = True
            result["pattern_type"] = "volume_price_spike"
            result["confidence"] = min(100, price_change * volume_change / 1000)
            result["details"]["price_change"] = price_change
            result["details"]["volume_change"] = volume_change

    if len(prices) > 10:
        steps = 0
        for i in range(1, min(10, len(prices))):
            if prices[-i] > prices[-i - 1] * 1.03:
                steps += 1
        if steps >= 3:
            result["is_pump"] = True
            result["pattern_type"] = "stair_step"
            result["confidence"] = min(100, steps * 15)
            result["details"]["steps"] = steps

    if len(prices) > 10 and len(volumes) > 10:
        avg_volume = sum(volumes[-10:-5]) / 5
        recent_volume = sum(volumes[-5:]) / 5
        price_change = ((prices[-1] - prices[-6]) / prices[-6]) * 100 if prices[-6] > 0 else 0
        if price_change > 20 and recent_volume < avg_volume * 0.8:
            result["is_pump"] = True
            result["pattern_type"] = "manipulated_jump"
            result["confidence"] = min(100, price_change * 2)
            result["details"]["price_change"] = price_change
            result["details"]["volume_ratio"] = recent_volume / (avg_volume + 0.0000001)

    return result


def detect_dump_pattern(analyzer, mint_address, window=20):
    """Özel dump desenlerini tespit eder."""
    if mint_address not in analyzer.price_history or len(analyzer.price_history[mint_address]) < window:
        return {
            "is_dump": False,
            "pattern_type": None,
            "confidence": 0,
            "details": {},
        }

    prices = [item["price"] for item in analyzer.price_history[mint_address][-window:]]
    volumes = (
        [item["volume"] for item in analyzer.volume_history[mint_address][-window:]]
        if mint_address in analyzer.volume_history and len(analyzer.volume_history[mint_address]) >= window
        else []
    )

    # Veri tipi kontrolü
    if not all(isinstance(p, (int, float)) for p in prices):
        prices = [p for p in prices if isinstance(p, (int, float))]
        if not prices:
            return {
                "is_dump": False,
                "pattern_type": None,
                "confidence": 0,
                "details": {},
            }
            
    if volumes and not all(isinstance(v, (int, float)) for v in volumes):
        volumes = [v for v in volumes if isinstance(v, (int, float))]

    result = {
        "is_dump": False,
        "pattern_type": None,
        "confidence": 0,
        "details": {},
    }

    if len(prices) > 5:
        price_change = ((prices[-1] - prices[-2]) / prices[-2]) * 100 if prices[-2] > 0 else 0
        price_change_5 = ((prices[-1] - prices[-6]) / prices[-6]) * 100 if len(prices) >= 6 and prices[-6] > 0 else 0
        if price_change < -10 or price_change_5 < -25:
            result["is_dump"] = True
            result["pattern_type"] = "sharp_drop"
            result["confidence"] = min(100, abs(price_change) * 2)
            result["details"]["price_change_1m"] = price_change
            result["details"]["price_change_5m"] = price_change_5

    if len(prices) > 5 and len(volumes) > 5:
        price_change = ((prices[-1] - prices[-2]) / prices[-2]) * 100 if prices[-2] > 0 else 0
        volume_change = ((volumes[-1] - volumes[-2]) / volumes[-2]) * 100 if volumes[-2] > 0 else 0
        if price_change < -5 and volume_change > 100:
            result["is_dump"] = True
            result["pattern_type"] = "high_volume_selloff"
            result["confidence"] = min(100, abs(price_change) * volume_change / 500)
            result["details"]["price_change"] = price_change
            result["details"]["volume_change"] = volume_change

    if hasattr(analyzer, "whale_transactions") and mint_address in analyzer.whale_transactions:
        recent_sales = [
            tx for tx in analyzer.whale_transactions[mint_address]
            if tx["type"] == "sell" and (datetime.now() - tx["timestamp"]).total_seconds() < 300
        ]
        total_sold = sum(tx["amount_sol"] for tx in recent_sales)
        
        whale_dump_threshold = analyzer.config.get("whale_dump_threshold", 10) if hasattr(analyzer, "config") else 10
            
        if total_sold > whale_dump_threshold and len(prices) > 5:
            price_change = ((prices[-1] - prices[-6]) / prices[-6]) * 100 if len(prices) >= 6 and prices[-6] > 0 else 0
            if price_change < -5:
                result["is_dump"] = True
                result["pattern_type"] = "whale_dump"
                result["confidence"] = min(100, abs(price_change) * total_sold / 10)
                result["details"]["price_change"] = price_change
                result["details"]["total_sold"] = total_sold

    return result


def detect_micro_pump(analyzer, mint_address, window=None):
    """Mikro pump tespiti."""
    if window is None:
        if hasattr(analyzer, "config"):
            micro_pump_interval = analyzer.config.get("micro_pump_interval", 60)
            rapid_cycle_interval = analyzer.config.get("rapid_cycle_interval", 5)
            window = max(2, int(micro_pump_interval / rapid_cycle_interval))
        else:
            window = 12  # Varsayılan değer
            
    if mint_address not in analyzer.price_history or len(analyzer.price_history[mint_address]) < window:
        return 0
    
    prices = [item["price"] for item in analyzer.price_history[mint_address][-window:]]
    
    if not prices or not all(isinstance(p, (int, float)) for p in prices):
        return 0
        
    if prices[0] <= 0:
        return 0
    
    price_change = ((prices[-1] - prices[0]) / prices[0]) * 100
    return price_change


def detect_whale_dump(analyzer, mint_address, window=10):
    """Balina satışlarını tespit et."""
    if not hasattr(analyzer, "whale_transactions") or mint_address not in analyzer.whale_transactions:
        return False, 0
    
    now = datetime.now()
    recent_transactions = [
        tx for tx in analyzer.whale_transactions[mint_address]
        if (now - tx["timestamp"]).total_seconds() < window * 60 and tx["type"] == "sell"
    ]
    
    if not recent_transactions:
        return False, 0
    
    total_sold = sum(tx["amount_sol"] for tx in recent_transactions)
    
    whale_dump_threshold = analyzer.config.get("whale_dump_threshold", 10) if hasattr(analyzer, "config") else 10
        
    threshold_triggered = total_sold >= whale_dump_threshold
    return threshold_triggered, total_sold
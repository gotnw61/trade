# -*- coding: utf-8 -*-
"""
Tahmin yapan fonksiyonlar
"""

import numpy as np
import time
from sklearn.ensemble import IsolationForest
import pandas as pd
from gotnw_tradebot.utils.logging_utils import log_to_file
from gotnw_tradebot.analysis.feature_extraction import extract_features

def predict_pump_with_ai(analyzer, mint_address, price, volume, momentum, volatility):
    """Yapay zeka ile pump tahmini yap"""
    # Veri tipi kontrolü
    if not isinstance(price, (int, float)):
        price = float(price) if hasattr(price, "__float__") else 0
    if not isinstance(volume, (int, float)):
        volume = float(volume) if hasattr(volume, "__float__") else 0
    if not isinstance(momentum, (int, float)):
        momentum = float(momentum) if hasattr(momentum, "__float__") else 0
    if not isinstance(volatility, (int, float)):
        volatility = float(volatility) if hasattr(volatility, "__float__") else 0
        
    if analyzer.pump_detection_model is not None:
        features = extract_features(analyzer, mint_address)
        if not features:
            return _basic_pump_prediction(analyzer, price, volume, momentum, volatility)

        try:
            df_features = pd.DataFrame([features])
            df_features = df_features.fillna(0)
            start_time = time.time()
            pump_proba = analyzer.pump_detection_model.predict_proba(df_features)[0, 1]
            
            threshold = 0.7
            if hasattr(analyzer, 'config'):
                threshold = analyzer.config.get("ai_confidence_threshold", 0.7)
                
            is_pump = pump_proba >= threshold
            inference_time = time.time() - start_time
            analyzer.inference_times.append(inference_time)
            return is_pump, pump_proba
        except Exception as e:
            log_to_file(f"Gelişmiş AI pump tahmini hatası: {e}")
            return _basic_pump_prediction(analyzer, price, volume, momentum, volatility)
    else:
        return _basic_pump_prediction(analyzer, price, volume, momentum, volatility)

def _basic_pump_prediction(analyzer, price, volume, momentum, volatility):
    """Temel pump tahmini"""
    # Veri tipi kontrolü
    if not isinstance(price, (int, float)):
        price = float(price) if hasattr(price, "__float__") else 0
    if not isinstance(volume, (int, float)):
        volume = float(volume) if hasattr(volume, "__float__") else 0
    if not isinstance(momentum, (int, float)):
        momentum = float(momentum) if hasattr(momentum, "__float__") else 0
    if not isinstance(volatility, (int, float)):
        volatility = float(volatility) if hasattr(volatility, "__float__") else 0
        
    features = np.array([[price, volume, momentum, volatility]])
    
    if len(analyzer.price_history.keys()) < 5:
        if momentum > 5 and volatility > 5:
            return True, 0.8
        return False, 0.2
    
    try:
        if not hasattr(analyzer, 'isolation_forest') or analyzer.isolation_forest is None:
            analyzer.isolation_forest = IsolationForest(contamination=0.05, random_state=42)
            
        is_fitted = getattr(analyzer.isolation_forest, "_fitted", False)
        
        if not is_fitted:
            training_data = []
            for mint in list(analyzer.price_history.keys())[:30]:
                if len(analyzer.price_history[mint]) > 5:
                    curr_price = analyzer.price_history[mint][-1]["price"]
                    if len(analyzer.price_history[mint]) > 10:
                        start_price = analyzer.price_history[mint][-10]["price"]
                        curr_momentum = ((curr_price - start_price) / max(0.0000001, start_price)) * 100
                    else:
                        curr_momentum = 0
                    prices = [entry["price"] for entry in analyzer.price_history[mint][-10:]]
                    curr_volatility = np.std(prices) * 100 if len(prices) > 1 else 0
                    training_data.append([curr_price, 0, curr_momentum, curr_volatility])
            
            if len(training_data) >= 10:
                analyzer.isolation_forest.fit(np.array(training_data))
                setattr(analyzer.isolation_forest, "_fitted", True)
                log_to_file("Isolation Forest modeli başarıyla eğitildi.")
            else:
                momentum_threshold = 5
                volatility_threshold = 5
                if hasattr(analyzer, 'config'):
                    momentum_threshold = analyzer.config.get("momentum_threshold", 5)
                    volatility_threshold = analyzer.config.get("volatility_threshold", 5)
                is_pump = momentum > momentum_threshold and volatility > volatility_threshold
                return is_pump, 0.6
        else:
            momentum_threshold = 5
            volatility_threshold = 5
            if hasattr(analyzer, 'config'):
                momentum_threshold = analyzer.config.get("momentum_threshold", 5)
                volatility_threshold = analyzer.config.get("volatility_threshold", 5)
            is_pump = momentum > momentum_threshold and volatility > volatility_threshold
            return is_pump, 0.5
    except Exception as e:
        log_to_file(f"Basit AI tahmini hatası: {e}")
        momentum_threshold = 5
        volatility_threshold = 5
        if hasattr(analyzer, 'config'):
            momentum_threshold = analyzer.config.get("momentum_threshold", 5)
            volatility_threshold = analyzer.config.get("volatility_threshold", 5)
        is_pump = momentum > momentum_threshold and volatility > volatility_threshold
        return is_pump, 0.5

def predict_pump_duration(analyzer, mint_address, momentum=None, volatility=None, volume=None):
    """Token için pump süresini tahmin eder"""
    # Veri tipi kontrolü
    if momentum is not None and not isinstance(momentum, (int, float)):
        momentum = float(momentum) if hasattr(momentum, "__float__") else None
    if volatility is not None and not isinstance(volatility, (int, float)):
        volatility = float(volatility) if hasattr(volatility, "__float__") else None
    if volume is not None and not isinstance(volume, (int, float)):
        volume = float(volume) if hasattr(volume, "__float__") else None
        
    if analyzer.pump_duration_model is not None:
        features = extract_features(analyzer, mint_address)
        if not features:
            return _basic_duration_prediction(analyzer, mint_address, momentum, volatility, volume)

        try:
            df_features = pd.DataFrame([features])
            df_features = df_features.fillna(0)
            duration = max(0, int(analyzer.pump_duration_model.predict(df_features)[0]))
            return duration
        except Exception as e:
            log_to_file(f"Gelişmiş pump süresi tahmini hatası: {e}")
            return _basic_duration_prediction(analyzer, mint_address, momentum, volatility, volume)
    else:
        return _basic_duration_prediction(analyzer, mint_address, momentum, volatility, volume)

def _basic_duration_prediction(analyzer, mint_address, momentum=None, volatility=None, volume=None):
    """Basit pump süresi tahmini"""
    try:
        if momentum is None:
            momentum = analyzer.calculate_momentum(mint_address)
        if volatility is None:
            volatility = analyzer.calculate_volatility(mint_address)
        if volume is None and mint_address in analyzer.volume_history and len(analyzer.volume_history[mint_address]) > 0:
            volume = analyzer.volume_history[mint_address][-1]["volume"]
        else:
            volume = 0

        # Veri tipi kontrolü
        if not isinstance(momentum, (int, float)):
            momentum = 0
        if not isinstance(volatility, (int, float)):
            volatility = 0
        if not isinstance(volume, (int, float)):
            volume = 0

        min_pump_duration_seconds = 30
        if hasattr(analyzer, 'config'):
            min_pump_duration_seconds = analyzer.config.get("min_pump_duration_seconds", 30)
            
        base_duration = min_pump_duration_seconds
        if momentum < 10 and volume > 10000:
            duration_estimate = base_duration * 3
        elif momentum > 20 and volatility > 15:
            duration_estimate = base_duration
        else:
            duration_estimate = base_duration * 2
            
        if hasattr(analyzer, 'last_pump_durations') and analyzer.last_pump_durations:
            avg_duration = sum(analyzer.last_pump_durations) / len(analyzer.last_pump_durations)
            duration_estimate = (duration_estimate + avg_duration) / 2
            
        return max(min_pump_duration_seconds, int(duration_estimate))
    except Exception as e:
        log_to_file(f"Pump süresi tahmini hatası: {e}")
        min_pump_duration_seconds = 30
        if hasattr(analyzer, 'config'):
            min_pump_duration_seconds = analyzer.config.get("min_pump_duration_seconds", 30)
        return min_pump_duration_seconds

def predict_future_price(analyzer, mint_address, minutes_ahead=10):
    """Token için gelecekteki fiyatı tahmin eder"""
    if not hasattr(analyzer, 'price_prediction_model') or analyzer.price_prediction_model is None:
        log_to_file(f"Fiyat tahmin modeli henüz eğitilmemiş!")
        return None

    features = extract_features(analyzer, mint_address)
    if not features:
        return None  # Placeholder for future price prediction logic
        
    df_features = pd.DataFrame([features])
    df_features = df_features.fillna(0)

    try:
        future_price = analyzer.price_prediction_model.predict(df_features)[0]
        return future_price
    except Exception as e:
        log_to_file(f"Fiyat tahmini hatası: {e}")
        return None
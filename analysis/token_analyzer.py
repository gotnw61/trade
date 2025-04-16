# -*- coding: utf-8 -*-
"""
Temel ve Gelişmiş Token Analiz Sınıfları
"""

import asyncio
import pickle
import time
from collections import defaultdict
from datetime import datetime, timedelta

import numpy as np

from gotnw_tradebot.config import trade_settings
from gotnw_tradebot.utils.logging_utils import log_to_file
from gotnw_tradebot.analysis.feature_extraction import extract_features
from gotnw_tradebot.analysis.price_patterns import (
    detect_dip,
    detect_pump_pattern,
    detect_dump_pattern,
    detect_micro_pump,
    detect_whale_dump,
)
from gotnw_tradebot.analysis.prediction import (
    predict_pump_with_ai,
    predict_pump_duration,
    predict_future_price,
)
from gotnw_tradebot.analysis.token_models import (
    train_pump_detection_model,
    train_pump_duration_model,
    train_price_prediction_model,
    train_ensemble_model,
)


class TokenAnalyzer:
    """Basit token analiz sınıfı."""
    
    def __init__(self):
        self.price_history = {}
        self.volume_history = {}
        self.liquidity_history = {}
        self.positions = {}
        self.price_queue = asyncio.Queue()
        self.active_subscriptions = {}

    def update_log(self, mint_address, message):
        """Loglama fonksiyonu."""
        log_to_file(f"{mint_address}: {message}")

    def update_price_history(self, mint_address, price, timestamp=None):
        """Fiyat geçmişini güncelle."""
        if timestamp is None:
            timestamp = datetime.now()
        if mint_address not in self.price_history:
            self.price_history[mint_address] = []
        self.price_history[mint_address].append({"timestamp": timestamp, "price": price})
        if len(self.price_history[mint_address]) > 1000:
            self.price_history[mint_address] = self.price_history[mint_address][-1000:]

    def update_volume_history(self, mint_address, volume, timestamp=None):
        """Hacim geçmişini güncelle."""
        if timestamp is None:
            timestamp = datetime.now()
        if mint_address not in self.volume_history:
            self.volume_history[mint_address] = []
        self.volume_history[mint_address].append({"timestamp": timestamp, "volume": volume})
        if len(self.volume_history[mint_address]) > 1000:
            self.volume_history[mint_address] = self.volume_history[mint_address][-1000:]

    def update_liquidity_history(self, mint_address, liquidity, timestamp=None):
        """Likidite geçmişini güncelle."""
        if timestamp is None:
            timestamp = datetime.now()
        if mint_address not in self.liquidity_history:
            self.liquidity_history[mint_address] = []
        self.liquidity_history[mint_address].append({"timestamp": timestamp, "liquidity": liquidity})
        if len(self.liquidity_history[mint_address]) > 1000:
            self.liquidity_history[mint_address] = self.liquidity_history[mint_address][-1000:]

    def calculate_momentum(self, mint_address, window=None):
        """Momentum hesapla."""
        if window is None:
            window = trade_settings.get("momentum_window", 20)
        
        if mint_address not in self.price_history:
            return 0
        
        prices = [item["price"] for item in self.price_history[mint_address][-window-1:]]
        
        if len(prices) < window + 1 or not all(isinstance(p, (int, float)) for p in prices):
            return 0
        
        start_price = prices[0]
        end_price = prices[-1]
        
        if start_price <= 0:
            return 0
        
        try:
            momentum = ((end_price - start_price) / start_price) * 100
            return momentum if isinstance(momentum, (int, float)) else 0
        except Exception as e:
            self.update_log(mint_address, f"Momentum hesaplamasında hata: {e}")
            return 0

    def calculate_volatility(self, mint_address, window=20):
        """Volatilite hesapla."""
        if mint_address not in self.price_history:
            return 0
        
        prices = [item["price"] for item in self.price_history[mint_address][-window:]]
        
        if len(prices) < window or not all(isinstance(p, (int, float)) for p in prices):
            return 0
        
        if not prices or min(prices) <= 0:
            return 0
        
        try:
            returns = [np.log(prices[i + 1] / prices[i]) for i in range(len(prices) - 1)]
            if not returns:
                return 0
            volatility = np.std(returns) * 100
            return volatility if isinstance(volatility, (int, float)) else 0
        except Exception as e:
            self.update_log(mint_address, f"Volatilite hesaplamasında hata: {e}")
            return 0

    def detect_liquidity_change(self, mint_address, current_liquidity, window=10):
        """Likidite değişimi tespiti."""
        if not isinstance(current_liquidity, (int, float)):
            self.update_log(mint_address, f"❌ Geçersiz likidite tipi: {type(current_liquidity)}")
            return 0

        if mint_address not in self.liquidity_history or len(self.liquidity_history[mint_address]) < window:
            return 0

        past_liquidity = [item["liquidity"] for item in self.liquidity_history[mint_address][-window:]]
        if not past_liquidity or not all(isinstance(l, (int, float)) for l in past_liquidity) or min(past_liquidity) <= 0:
            return 0

        try:
            avg_liquidity = np.mean(past_liquidity)
            if avg_liquidity <= 0:
                return 0
            liquidity_change = ((current_liquidity - avg_liquidity) / avg_liquidity) * 100
            return liquidity_change
        except Exception as e:
            self.update_log(mint_address, f"Likidite değişimi hesaplama hatası: {e}")
            return 0
    
    def detect_price_deviation(self, mint_address, current_price, window=20):
        """Fiyat sapmasını tespit et."""
        if not isinstance(current_price, (int, float)):
            self.update_log(mint_address, f"❌ Geçersiz fiyat tipi: {type(current_price)}")
            return 0
            
        if mint_address not in self.price_history or len(self.price_history[mint_address]) < window:
            return 0
        prices = [item["price"] for item in self.price_history[mint_address][-window:]]
        if not prices:
            return 0
        mean_price = np.mean(prices)
        std_price = np.std(prices)
        if std_price == 0:
            return 0
        z_score = (current_price - mean_price) / std_price
        return z_score
    
    def detect_volume_drop(self, mint_address, current_volume, window=10):
        """Hacim düşüşünü tespit et."""
        if not isinstance(current_volume, (int, float)):
            self.update_log(mint_address, f"❌ Geçersiz hacim tipi: {type(current_volume)}")
            return 0
            
        if mint_address not in self.volume_history or len(self.volume_history[mint_address]) < window:
            return 0
        past_volumes = [item["volume"] for item in self.volume_history[mint_address][-window:]]
        
        if not past_volumes or not all(isinstance(v, (int, float)) for v in past_volumes):
            return 0
            
        avg_volume = np.mean(past_volumes)
        if avg_volume <= 0:
            return 0
        volume_drop = ((avg_volume - current_volume) / avg_volume) * 100
        return max(0, volume_drop)

    async def analyze_token_dynamics(self, mint_address, current_price, token_info, price_change_pct):
        """Token dinamiklerini analiz eder."""
        try:
            # Veri tiplerinin kontrolü
            if not isinstance(current_price, (int, float)):
                current_price = float(current_price) if hasattr(current_price, "__float__") else 0
                self.update_log(mint_address, f"⚠️ Geçersiz fiyat tipi dönüştürüldü: {type(current_price)}")
            
            if not isinstance(token_info, dict):
                token_info = {} if token_info is None else {"price_usd": current_price}
                self.update_log(mint_address, f"⚠️ Geçersiz token_info tipi dönüştürüldü: {type(token_info)}")
                
            # Token pozisyonunda mı kontrolü
            in_position = mint_address in self.positions
            
            # Analizleri yap
            momentum = self.calculate_momentum(mint_address)
            volatility = self.calculate_volatility(mint_address)
            
            # Token_info içinden değerleri güvenli şekilde al
            liquidity_usd = token_info.get("liquidity_usd", 0)
            if not isinstance(liquidity_usd, (int, float)):
                liquidity_usd = 0
                
            liquidity_change = self.detect_liquidity_change(mint_address, liquidity_usd)
            price_deviation = self.detect_price_deviation(mint_address, current_price)
            
            # Dip tespiti
            dip_result = detect_dip(self, mint_address, current_price)
            dip_percentage = dip_result["metrics"]["dip_percentage"] if isinstance(dip_result, dict) and "metrics" in dip_result else 0
            
            volume = token_info.get("volume", 0)
            if not isinstance(volume, (int, float)):
                volume = 0
                
            volume_drop = self.detect_volume_drop(mint_address, volume)
            
            # Dinamik analiz sonuçlarını toplama
            dynamics = {
                "in_position": in_position,
                "momentum": momentum,
                "volatility": volatility,
                "liquidity_change": liquidity_change,
                "price_deviation": price_deviation,
                "dip_percentage": dip_percentage,
                "volume_drop": volume_drop,
            }
            return dynamics
        except Exception as e:
            self.update_log(mint_address, f"Token dinamiği analiz hatası: {e}")
            import traceback
            traceback.print_exc()
            return None


class EnhancedTokenAnalyzer(TokenAnalyzer):
    """
    Gelişmiş token analiz sınıfı.
    Daha kapsamlı analiz ve yapay zeka tahminleri sunar.
    """

    def __init__(self):
        super().__init__()
        self.transaction_history = defaultdict(list)
        self.whale_transactions = defaultdict(list)
        self.token_categories = {}
        self.volatility_data = {}
        self.pump_predictions = {}

        # Modeller
        self.scaler = None
        self.isolation_forest = None
        self.pump_detection_model = None
        self.pump_duration_model = None
        self.price_prediction_model = None
        self.ensemble_model = None

        # Model performans metrikleri
        self.model_metrics = {
            "pump_detection": {"precision": 0, "recall": 0, "f1": 0},
            "pump_duration": {"mae": 0, "mse": 0, "r2": 0},
            "price_prediction": {"mae": 0, "mse": 0, "r2": 0},
            "ensemble": {"precision": 0, "recall": 0, "f1": 0},
        }

        # Özellik önem dereceleri
        self.feature_importances = {}

        # Model çalışma zamanı performansı
        self.inference_times = []

        # Pump süresi verileri
        self.last_pump_durations = []

    def categorize_token(self, token_info):
        """Token sınıflandırması için basit bir yöntem."""
        if not token_info:
            return "unknown"
        liquidity = token_info.get("liquidity_usd", 0)
        market_cap = token_info.get("market_cap", 0)
        volume = token_info.get("volume", 0)
        if liquidity > 100000 and market_cap > 1000000:
            return "established"
        elif liquidity > 20000 and market_cap > 100000:
            return "mid_cap"
        elif liquidity > 5000:
            return "low_cap"
        else:
            return "micro_cap"

    def record_whale_transaction(self, mint_address, amount_sol, transaction_type, timestamp=None):
        """Balina işlemlerini kaydet."""
        if timestamp is None:
            timestamp = datetime.now()
        if amount_sol >= trade_settings["whale_threshold_sol"]:
            self.whale_transactions[mint_address].append({
                "timestamp": timestamp,
                "amount_sol": amount_sol,
                "type": transaction_type,
            })
            if len(self.whale_transactions[mint_address]) > 100:
                self.whale_transactions[mint_address] = self.whale_transactions[mint_address][-100:]

            # Ayrıca genel işlem geçmişine de kaydet
            self.record_transaction(
                mint_address,
                amount_sol,
                transaction_type,
                price=None,
                timestamp=timestamp,
            )

    def record_transaction(self, mint_address, amount, transaction_type, price=None, timestamp=None):
        """İşlem verilerini kaydeder."""
        if timestamp is None:
            timestamp = datetime.now()

        self.transaction_history[mint_address].append({
            "timestamp": timestamp,
            "amount": amount,
            "type": transaction_type,
            "price": price,
        })

        # Geçmiş verileri sınırla (örn. son 1000 işlem)
        max_transactions = 1000
        if len(self.transaction_history[mint_address]) > max_transactions:
            self.transaction_history[mint_address] = self.transaction_history[mint_address][-max_transactions:]

    def predict_pump(self, mint_address):
        """Token için pump tahmini yapar."""
        try:
            features = extract_features(self, mint_address)
            if not features:
                return False, 0

            current_price = features.get("current_price", 0)
            current_volume = features.get("current_volume", 0)
            momentum = self.calculate_momentum(mint_address)
            volatility = self.calculate_volatility(mint_address)

            is_pump, pump_probability = predict_pump_with_ai(
                self, mint_address, current_price, current_volume, momentum, volatility
            )
            return is_pump, pump_probability
        except Exception as e:
            log_to_file(f"Pump tahmini hatası: {e}")
            return False, 0

    def get_multi_confirmation_signal(self, mint_address):
        """
        Birden fazla göstergeyi kullanarak alım sinyali oluşturur.
        En az 1/3 gösterge olumlu olmalıdır (daha gevşek kural).
        """
        confirmations = 0
        total_indicators = 3
        signal_details = {}
        
        momentum = self.calculate_momentum(mint_address)
        momentum_threshold = trade_settings.get("momentum_threshold", 5) * 0.7
        momentum_signal = momentum >= momentum_threshold
        signal_details["momentum"] = {
            "value": momentum,
            "signal": momentum_signal,
            "threshold": momentum_threshold,
        }
        if momentum_signal:
            confirmations += 1
        
        price_change = 0
        if mint_address in self.price_history and len(self.price_history[mint_address]) >= 5:
            prices = [item["price"] for item in self.price_history[mint_address][-5:]]
            if prices[0] > 0:
                price_change = ((prices[-1] - prices[0]) / prices[0]) * 100
        price_change_signal = price_change >= 3
        signal_details["price_change"] = {
            "value": price_change,
            "signal": price_change_signal,
            "threshold": 3,
        }
        if price_change_signal:
            confirmations += 1
        
        volume_increase = 0
        if mint_address in self.volume_history and len(self.volume_history[mint_address]) >= 2:
            volumes = [item["volume"] for item in self.volume_history[mint_address][-2:]]
            if volumes[0] > 0:
                volume_increase = ((volumes[-1] - volumes[0]) / volumes[0]) * 100
        volume_signal = volume_increase >= 20
        
        # Güvenli şekilde current_price al
        current_price = 0
        if mint_address in self.price_history and len(self.price_history[mint_address]) > 0:
            price_item = self.price_history[mint_address][-1]
            if isinstance(price_item, dict) and "price" in price_item:
                current_price = price_item["price"]
            elif isinstance(price_item, (int, float)):
                current_price = price_item
                
        # trade_settings içinden fast_buy_threshold al
        fast_buy_threshold = trade_settings.get("fast_buy_threshold", 0)
        is_fast_buy = current_price >= fast_buy_threshold
        
        combined_signal = volume_signal or is_fast_buy
        if combined_signal:
            confirmations += 1
        
        signal_details["volume_or_fast_buy"] = {
            "volume_increase": volume_increase,
            "volume_signal": volume_signal,
            "is_fast_buy": is_fast_buy,
            "combined_signal": combined_signal,
        }
        
        is_confirmed = confirmations >= 1
        confidence = (confirmations / total_indicators) * 100
        
        return {
            "is_confirmed": is_confirmed,
            "confirmations": confirmations,
            "total_indicators": total_indicators,
            "confidence": confidence,
            "details": signal_details,
        }

    def check_rapid_price_increase(self, mint_address, threshold=50, window=10):
        """Kısa süre içinde hızlı fiyat artışı olup olmadığını kontrol eder."""
        if mint_address not in self.price_history or len(self.price_history[mint_address]) < window:
            return {
                "is_rapid_increase": False,
                "increase_percentage": 0,
                "is_risky": False,
            }
        
        prices = [item["price"] for item in self.price_history[mint_address][-window:]]
        
        # Veri tipi kontrolü
        if not all(isinstance(p, (int, float)) for p in prices):
            prices = [p for p in prices if isinstance(p, (int, float))]
            if not prices:
                return {
                    "is_rapid_increase": False,
                    "increase_percentage": 0,
                    "is_risky": False,
                }
                
        start_price = prices[0]
        current_price = prices[-1]
        
        if start_price <= 0:
            return {
                "is_rapid_increase": False,
                "increase_percentage": 0,
                "is_risky": False,
            }
        
        increase_percentage = ((current_price - start_price) / start_price) * 100
        is_rapid_increase = increase_percentage >= threshold
        is_risky = is_rapid_increase
        
        rsi = 0
        if len(prices) >= 14:
            gains = []
            losses = []
            for i in range(1, len(prices)):
                change = prices[i] - prices[i-1]
                if change > 0:
                    gains.append(change)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(change))
            
            avg_gain = sum(gains) / len(gains) if gains else 0.0001
            avg_loss = sum(losses) / len(losses) if losses else 0.0001
            rs = avg_gain / max(avg_loss, 0.0001)
            rsi = 100 - (100 / (1 + rs))
        
        is_overbought = rsi > 70
        
        half_index = len(prices) // 2
        if half_index > 0:
            first_half_increase = ((prices[half_index] - prices[0]) / prices[0]) * 100
            second_half_increase = ((prices[-1] - prices[half_index]) / prices[half_index]) * 100
            is_parabolic = second_half_increase > first_half_increase * 1.5
        else:
            is_parabolic = False
        
        is_very_risky = is_rapid_increase and (is_overbought or is_parabolic)
        
        return {
            "is_rapid_increase": is_rapid_increase,
            "increase_percentage": increase_percentage,
            "is_risky": is_risky,
            "is_very_risky": is_very_risky,
            "rsi": rsi,
            "is_overbought": is_overbought,
            "is_parabolic": is_parabolic if half_index > 0 else None,
            "recommendation": "skip" if is_very_risky else "caution" if is_risky else "proceed",
        }

    def analyze_token(self, mint_address):
        """Token için kapsamlı analiz yapar ve sonuçları rapor eder."""
        features = extract_features(self, mint_address)
        if not features:
            return "Bu token için yeterli veri yok."

        analysis_report = []
        analysis_report.append(f"Token Analizi: {mint_address}\n")
        analysis_report.append(f"Güncel Fiyat: ${features['current_price']:.10f}")

        for window in [5, 10, 20]:
            if f"price_change_{window}" in features:
                analysis_report.append(f"Son {window} veri noktasında fiyat değişimi: %{features[f'price_change_{window}']:.2f}")

        for window in [10, 20]:
            if f"volatility_{window}" in features:
                analysis_report.append(f"Son {window} veri noktasında volatilite: %{features[f'volatility_{window}']:.2f}")

        for window in [10, 20]:
            if f"rsi_{window}" in features:
                rsi = features[f"rsi_{window}"]
                rsi_status = "Aşırı satılmış" if rsi < 30 else "Aşırı alınmış" if rsi > 70 else "Normal"
                analysis_report.append(f"RSI ({window}): {rsi:.2f} - {rsi_status}")

        if "current_volume" in features:
            analysis_report.append(f"\nGüncel Hacim: ${features['current_volume']:.2f}")
            for window in [5, 10]:
                if f"volume_change_{window}" in features:
                    analysis_report.append(f"Son {window} veri noktasında hacim değişimi: %{features[f'volume_change_{window}']:.2f}")

        if "current_liquidity" in features:
            analysis_report.append(f"\nGüncel Likidite: ${features['current_liquidity']:.2f}")
            for window in [5, 10]:
                if f"liquidity_change_{window}" in features:
                    analysis_report.append(f"Son {window} veri noktasında likidite değişimi: %{features[f'liquidity_change_{window}']:.2f}")

        if "whale_tx_count_24h" in features and features["whale_tx_count_24h"] > 0:
            analysis_report.append(f"\nSon 24 saatte balina işlemleri:")
            analysis_report.append(f"Toplam işlem: {features['whale_tx_count_24h']}")
            analysis_report.append(f"Alım işlemleri: {features['whale_buy_count_24h']}")
            analysis_report.append(f"Satım işlemleri: {features['whale_sell_count_24h']}")
            analysis_report.append(f"Toplam alım hacmi: {features['whale_buy_volume_24h']:.2f} SOL")
            analysis_report.append(f"Toplam satım hacmi: {features['whale_sell_volume_24h']:.2f} SOL")

        analysis_report.append("\nModel Tahminleri:")
        is_pump, pump_proba = self.predict_pump(mint_address)
        pump_status = "YÜKSELİŞ BEKLENİYOR" if is_pump else "Yükseliş beklenmiyor"
        analysis_report.append(f"Pump Olasılığı: %{pump_proba * 100:.2f} - {pump_status}")

        if self.pump_duration_model and is_pump:
            duration = predict_pump_duration(self, mint_address)
            analysis_report.append(f"Tahmini Pump Süresi: {duration} veri noktası")

        if self.price_prediction_model:
            future_price = predict_future_price(self, mint_address)
            if future_price:
                price_change = ((future_price - features["current_price"]) / features["current_price"]) * 100
                analysis_report.append(f"10 dakika sonrası için fiyat tahmini: ${future_price:.10f} (%{price_change:.2f})")

        return "\n".join(analysis_report)

    def prepare_dataset(self, mint_addresses=None, label_window=10, feature_windows=[5, 10, 20, 50, 100]):
        """Eğitim için veri seti oluşturur."""
        from gotnw_tradebot.analysis.token_models import prepare_dataset
        return prepare_dataset(self, mint_addresses, label_window, feature_windows)
        
    def train_pump_detection_model(self, mint_addresses=None, test_size=0.2, random_state=42):
        """Pump algılama modeli eğitir."""
        return train_pump_detection_model(self, mint_addresses, test_size, random_state)
        
    def train_pump_duration_model(self, mint_addresses=None, test_size=0.2, random_state=42):
        """Pump süresi tahmin modeli eğitir."""
        return train_pump_duration_model(self, mint_addresses, test_size, random_state)
        
    def train_price_prediction_model(self, mint_addresses=None, test_size=0.2, random_state=42):
        """Fiyat tahmin modeli eğitir."""
        return train_price_prediction_model(self, mint_addresses, test_size, random_state)
        
    def train_ensemble_model(self, mint_addresses=None, test_size=0.2, random_state=42):
        """Ensemble model eğitir (birden fazla modelin birleşimi)."""
        return train_ensemble_model(self, mint_addresses, test_size, random_state)

    def update_pump_duration_history(self, actual_duration):
        """Gerçek pump sürelerini kaydet."""
        if not isinstance(actual_duration, (int, float)):
            actual_duration = int(actual_duration) if hasattr(actual_duration, "__int__") else 0
            
        self.last_pump_durations.append(actual_duration)
        if len(self.last_pump_durations) > 10:
            self.last_pump_durations = self.last_pump_durations[-10:]

    def save_models(self, filename_prefix="ai_models"):
        """Tüm modelleri kaydet."""
        if self.pump_detection_model:
            with open(f"{filename_prefix}_pump_detection.pkl", "wb") as f:
                pickle.dump(self.pump_detection_model, f)

        if self.pump_duration_model:
            with open(f"{filename_prefix}_pump_duration.pkl", "wb") as f:
                pickle.dump(self.pump_duration_model, f)

        if self.price_prediction_model:
            with open(f"{filename_prefix}_price_prediction.pkl", "wb") as f:
                pickle.dump(self.price_prediction_model, f)

        if self.ensemble_model:
            with open(f"{filename_prefix}_ensemble.pkl", "wb") as f:
                pickle.dump(self.ensemble_model, f)

        with open(f"{filename_prefix}_metrics.pkl", "wb") as f:
            pickle.dump(self.model_metrics, f)

        with open(f"{filename_prefix}_feature_importances.pkl", "wb") as f:
            pickle.dump(self.feature_importances, f)

        print(f"Modeller kaydedildi: {filename_prefix}_*.pkl")

    def load_models(self, filename_prefix="ai_models"):
        """Tüm modelleri yükle."""
        import os

        if os.path.exists(f"{filename_prefix}_pump_detection.pkl"):
            with open(f"{filename_prefix}_pump_detection.pkl", "rb") as f:
                self.pump_detection_model = pickle.load(f)

        if os.path.exists(f"{filename_prefix}_pump_duration.pkl"):
            with open(f"{filename_prefix}_pump_duration.pkl", "rb") as f:
                self.pump_duration_model = pickle.load(f)

        if os.path.exists(f"{filename_prefix}_price_prediction.pkl"):
            with open(f"{filename_prefix}_price_prediction.pkl", "rb") as f:
                self.price_prediction_model = pickle.load(f)

        if os.path.exists(f"{filename_prefix}_ensemble.pkl"):
            with open(f"{filename_prefix}_ensemble.pkl", "rb") as f:
                self.ensemble_model = pickle.load(f)

        if os.path.exists(f"{filename_prefix}_metrics.pkl"):
            with open(f"{filename_prefix}_metrics.pkl", "rb") as f:
                self.model_metrics = pickle.load(f)

        if os.path.exists(f"{filename_prefix}_feature_importances.pkl"):
            with open(f"{filename_prefix}_feature_importances.pkl", "rb") as f:
                self.feature_importances = pickle.load(f)

        print("Modeller yüklendi.")

    def predict_with_ensemble(self, mint_address):
        """Ensemble model ile tahmin yapar."""
        if not hasattr(self, "ensemble_model") or self.ensemble_model is None:
            return self.predict_pump(mint_address)

        features = extract_features(self, mint_address)
        if not features:
            return False, 0

        import pandas as pd
        df_features = pd.DataFrame([features])
        df_features = df_features.fillna(0)

        try:
            is_pump = self.ensemble_model.predict(df_features)[0]
            pump_proba = self.ensemble_model.predict_proba(df_features)[0, 1]
            return bool(is_pump), pump_proba
        except Exception as e:
            log_to_file(f"Ensemble tahmin hatası: {e}")
            return self.predict_pump(mint_address)

    def optimize_trading_strategy(self, token_history=None, risk_level="normal"):
        """İşlem stratejisini geçmiş verilere dayanarak optimize eder."""
        print("Strateji optimizasyonu başlatılıyor...")
        
        if token_history is None:
            if not hasattr(self, "past_trades"):
                self.past_trades = []
            token_history = self.past_trades
            
        if not token_history or len(token_history) < 10:
            print("Optimizasyon için yeterli veri yok.")
            return False
        
        profitable_trades = [trade for trade in token_history if trade.get("profit_loss", 0) > 0]
        losing_trades = [trade for trade in token_history if trade.get("profit_loss", 0) < 0]
        
        if not profitable_trades:
            print("Optimizasyon için kârlı işlem verisi bulunamadı.")
            return False
        
        avg_profit_pct = []
        for trade in profitable_trades:
            if trade.get("buy_price") and trade.get("sell_price") and trade.get("buy_price") > 0:
                profit_pct = ((trade.get("sell_price") - trade.get("buy_price")) / trade.get("buy_price")) * 100
                avg_profit_pct.append(profit_pct)
        
        avg_profit = sum(avg_profit_pct) / len(avg_profit_pct) if avg_profit_pct else 0
        
        avg_loss_pct = []
        for trade in losing_trades:
            if trade.get("buy_price") and trade.get("sell_price") and trade.get("buy_price") > 0:
                loss_pct = ((trade.get("sell_price") - trade.get("buy_price")) / trade.get("buy_price")) * 100
                avg_loss_pct.append(loss_pct)
        
        avg_loss = sum(avg_loss_pct) / len(avg_loss_pct) if avg_loss_pct else 0
        
        profit_percentiles = {}
        if avg_profit_pct:
            for p in [25, 50, 75, 90, 95]:
                profit_percentiles[p] = np.percentile(avg_profit_pct, p)
        
        loss_percentiles = {}
        if avg_loss_pct:
            for p in [5, 10, 25, 50, 75]:
                loss_percentiles[p] = np.percentile(avg_loss_pct, p)
        
        risk_multiplier = {"low": 0.7, "normal": 1.0, "high": 1.3}.get(risk_level, 1.0)
        
        tp_levels = []
        if profit_percentiles:
            tp_levels = [
                {"profit": max(5, min(20, profit_percentiles.get(25, 10) * risk_multiplier)), "sell_percentage": 25},
                {"profit": max(15, min(50, profit_percentiles.get(50, 25) * risk_multiplier)), "sell_percentage": 25},
                {"profit": max(30, min(100, profit_percentiles.get(75, 50) * risk_multiplier)), "sell_percentage": 25},
                {"profit": max(50, min(200, profit_percentiles.get(90, 100) * risk_multiplier)), "sell_percentage": 25},
            ]
        else:
            tp_levels = [
                {"profit": 20 * risk_multiplier, "sell_percentage": 25},
                {"profit": 50 * risk_multiplier, "sell_percentage": 25},
                {"profit": 100 * risk_multiplier, "sell_percentage": 25},
                {"profit": 150 * risk_multiplier, "sell_percentage": 25},
            ]
        
        sl_levels = []
        if loss_percentiles:
            sl_levels = [
                {"loss": min(-3, max(-15, loss_percentiles.get(25, -5) * risk_multiplier)), "sell_percentage": 50},
                {"loss": min(-5, max(-25, loss_percentiles.get(10, -10) * risk_multiplier)), "sell_percentage": 50},
            ]
        else:
            sl_levels = [
                {"loss": -5 * risk_multiplier, "sell_percentage": 50},
                {"loss": -10 * risk_multiplier, "sell_percentage": 100},
            ]
        
        optimized_params = {
            "sell_profit_targets": tp_levels,
            "sell_stop_loss_levels": sl_levels,
            "trailing_stop_loss": max(3, min(10, abs(avg_loss) / 2)) * risk_multiplier,
            "momentum_threshold": max(3, min(10, avg_profit / 10)) * risk_multiplier,
            "dip_buy_threshold": max(5, min(25, abs(avg_loss) * 1.5)) * risk_multiplier,
            "micro_pump_threshold": max(2, min(8, avg_profit / 10)) * risk_multiplier,
        }
        
        print("Strateji optimizasyonu tamamlandı:")
        print(f"TP Seviyeleri: {tp_levels}")
        print(f"SL Seviyeleri: {sl_levels}")
        print(f"Trailing Stop Loss: {optimized_params['trailing_stop_loss']:.2f}%")
        
        return optimized_params
# -*- coding: utf-8 -*-
"""
AI model eğitimi ve veri seti hazırlama
"""

import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.ensemble import (
    AdaBoostClassifier,
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    IsolationForest,
    RandomForestClassifier,
    VotingClassifier,
)
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import f1_score, mean_absolute_error, mean_squared_error, precision_score, r2_score, recall_score
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.utils import resample

from gotnw_tradebot.analysis.feature_extraction import extract_features
from gotnw_tradebot.utils.logging_utils import log_to_file


def prepare_dataset(analyzer, mint_addresses=None, label_window=10, feature_windows=[5, 10, 20, 50, 100]):
    """Eğitim için veri seti oluşturur."""
    if mint_addresses is None:
        mint_addresses = list(analyzer.price_history.keys())

    all_features = []
    all_pump_labels = []
    all_duration_labels = []
    all_future_prices = []

    for mint in mint_addresses:
        if mint not in analyzer.price_history or len(analyzer.price_history[mint]) < max(feature_windows) + label_window:
            continue

        prices = [item["price"] for item in analyzer.price_history[mint]]
        timestamps = [item["timestamp"] for item in analyzer.price_history[mint]]

        # Veri tipi kontrolü
        if not all(isinstance(p, (int, float)) for p in prices):
            continue
            
        for i in range(max(feature_windows), len(prices) - label_window):
            current_timestamp = timestamps[i]
            filtered_prices = [{"timestamp": timestamps[j], "price": prices[j]} for j in range(i + 1)]
            temp_price_history = analyzer.price_history.copy()
            temp_price_history[mint] = filtered_prices

            temp_volume_history = None
            if mint in analyzer.volume_history:
                filtered_volumes = [vol for vol in analyzer.volume_history[mint] if vol["timestamp"] <= current_timestamp]
                temp_volume_history = analyzer.volume_history.copy()
                temp_volume_history[mint] = filtered_volumes

            temp_liquidity_history = None
            if mint in analyzer.liquidity_history:
                filtered_liquidity = [
                    liq for liq in analyzer.liquidity_history[mint] if liq["timestamp"] <= current_timestamp
                ]
                temp_liquidity_history = analyzer.liquidity_history.copy()
                temp_liquidity_history[mint] = filtered_liquidity

            orig_price_history = analyzer.price_history
            orig_volume_history = analyzer.volume_history
            orig_liquidity_history = analyzer.liquidity_history

            analyzer.price_history = temp_price_history
            if temp_volume_history:
                analyzer.volume_history = temp_volume_history
            if temp_liquidity_history:
                analyzer.liquidity_history = temp_liquidity_history

            features = extract_features(analyzer, mint, feature_windows)

            analyzer.price_history = orig_price_history
            analyzer.volume_history = orig_volume_history
            analyzer.liquidity_history = orig_liquidity_history

            if not features:
                continue

            current_price = prices[i]
            future_prices = prices[i + 1:i + 1 + label_window]
            max_future_price = max(future_prices)
            price_increase_pct = ((max_future_price - current_price) / current_price) * 100 if current_price > 0 else 0

            pump_threshold = 15.0
            is_pump = price_increase_pct >= pump_threshold

            pump_duration = 0
            if is_pump:
                for j in range(i + 1, i + 1 + label_window):
                    if j < len(prices) and prices[j] >= current_price * (1 + pump_threshold / 100):
                        pump_duration += 1
                    else:
                        break

            future_price_idx = min(i + label_window, len(prices) - 1)
            future_price = prices[future_price_idx]

            all_features.append(features)
            all_pump_labels.append(1 if is_pump else 0)
            all_duration_labels.append(pump_duration)
            all_future_prices.append(future_price)

    # Veri setlerini güvenli bir şekilde eşitleme
    def safe_truncate(features_list, labels_list, future_prices_list):
        min_length = min(len(features_list), len(labels_list), len(future_prices_list))
        return (
            features_list[:min_length],
            labels_list[:min_length],
            future_prices_list[:min_length],
        )

    # Modelleme öncesi veri setini güvenli bir şekilde hazırla
    def prepare_ml_dataset(features, labels, future_prices):
        features_df = pd.DataFrame(features)
        features_df = features_df.replace([np.inf, -np.inf], np.nan).dropna()
        features = features_df.to_dict("records")
        features, labels, future_prices = safe_truncate(features, labels, future_prices)
        return features, labels, future_prices

    all_features, all_pump_labels, all_future_prices = prepare_ml_dataset(
        all_features, all_pump_labels, all_future_prices
    )

    # Mevcut duration_labels'ı da eşitle
    all_duration_labels = all_duration_labels[:len(all_features)]

    return all_features, all_pump_labels, all_duration_labels, all_future_prices


def train_pump_detection_model(analyzer, mint_addresses=None, test_size=0.2, random_state=42):
    """Pump algılama modeli eğitir."""
    print("Pump algılama modeli eğitiliyor...")

    features, pump_labels, _, _ = prepare_dataset(analyzer, mint_addresses)
    
    # Minimum veri kontrolü
    if len(features) < 20:  # Daha esnek bir eşik
        print("Eğitim için yeterli veri yok!")
        return False

    # Dengesiz veri seti için gelişmiş handling
    def balance_dataset(features, labels):
        """Sınıf dengesizliğini giderir."""
        pump_samples = [f for f, l in zip(features, labels) if l == 1]
        normal_samples = [f for f, l in zip(features, labels) if l == 0]
        
        print(f"Pump örnekleri: {len(pump_samples)}, Normal örnekler: {len(normal_samples)}")
        
        if len(pump_samples) == 0:
            print("❌ Hiç pump örneği bulunamadı!")
            return features, labels
        
        if len(pump_samples) < len(normal_samples):
            try:
                if len(pump_samples) <= 5:
                    print("⚠️ Çok az pump örneği, örnekleme yapılmayacak")
                    return features, labels
                
                pump_samples = resample(
                    pump_samples,
                    replace=True,
                    n_samples=len(normal_samples),
                    random_state=random_state,
                )
            except ValueError as e:
                print(f"❌ Örnekleme hatası: {e}")
                return features, labels
        
        balanced_features = pump_samples + normal_samples
        balanced_labels = [1] * len(pump_samples) + [0] * len(normal_samples)
        
        return balanced_features, balanced_labels

    try:
        features, pump_labels = balance_dataset(features, pump_labels)
    except Exception as e:
        print(f"❌ Veri dengelenemedi: {e}")
        return False

    feature_names = list(features[0].keys())
    df_features = pd.DataFrame(features)
    df_labels = pd.Series(pump_labels)
    df_features = df_features.fillna(0)

    X_train, X_test, y_train, y_test = train_test_split(
        df_features, df_labels, test_size=test_size, random_state=random_state
    )

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", GradientBoostingClassifier(random_state=random_state)),
    ])

    param_grid = {
        "classifier__n_estimators": [50, 100, 200],
        "classifier__learning_rate": [0.01, 0.05, 0.1, 0.2],
        "classifier__max_depth": [3, 4, 5, 6],
        "classifier__min_samples_split": [2, 5, 10],
        "classifier__subsample": [0.8, 0.9, 1.0],
    }

    grid_search = GridSearchCV(
        pipeline,
        param_grid,
        cv=3,
        scoring="f1",
        n_jobs=-1 if len(X_train) > 100 else 1,
    )

    try:
        print("Hyperparameter optimizasyonu başlatılıyor...")
        grid_search.fit(X_train, y_train)
        print(f"En iyi parametreler: {grid_search.best_params_}")
        print(f"En iyi çapraz doğrulama skoru: {grid_search.best_score_:.4f}")
        best_model = grid_search.best_estimator_
    except Exception as e:
        print(f"Hyperparameter optimizasyonu sırasında hata: {e}")
        print("Varsayılan parametrelerle devam ediliyor...")
        best_model = Pipeline([
            ("scaler", StandardScaler()),
            (
                "classifier",
                GradientBoostingClassifier(
                    n_estimators=100,
                    learning_rate=0.1,
                    max_depth=5,
                    random_state=random_state,
                ),
            ),
        ])
        best_model.fit(X_train, y_train)

    y_pred = best_model.predict(X_test)
    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)

    analyzer.model_metrics["pump_detection"]["precision"] = precision
    analyzer.model_metrics["pump_detection"]["recall"] = recall
    analyzer.model_metrics["pump_detection"]["f1"] = f1

    feature_importances = best_model.named_steps["classifier"].feature_importances_
    analyzer.feature_importances["pump_detection"] = dict(zip(feature_names, feature_importances))
    analyzer.pump_detection_model = best_model

    print(f"Pump algılama modeli eğitildi. F1 Skoru: {f1:.4f}")
    return True


def train_pump_duration_model(analyzer, mint_addresses=None, test_size=0.2, random_state=42):
    """Pump süresi tahmin modeli eğitir."""
    print("Pump süresi tahmin modeli eğitiliyor...")

    features, pump_labels, duration_labels, _ = prepare_dataset(analyzer, mint_addresses)
    pump_indices = [i for i, label in enumerate(pump_labels) if label == 1]

    if len(pump_indices) < 10:
        print("Eğitim için yeterli pump verisi yok!")
        return False

    pump_features = [features[i] for i in pump_indices]
    pump_durations = [duration_labels[i] for i in pump_indices]

    feature_names = list(pump_features[0].keys())
    df_features = pd.DataFrame(pump_features)
    df_labels = pd.Series(pump_durations)
    df_features = df_features.fillna(0)

    X_train, X_test, y_train, y_test = train_test_split(
        df_features, df_labels, test_size=test_size, random_state=random_state
    )

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        (
            "regressor",
            GradientBoostingRegressor(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=4,
                random_state=random_state,
            ),
        ),
    ])

    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)

    mae = mean_absolute_error(y_test, y_pred)
    mse = mean_squared_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    analyzer.model_metrics["pump_duration"]["mae"] = mae
    analyzer.model_metrics["pump_duration"]["mse"] = mse
    analyzer.model_metrics["pump_duration"]["r2"] = r2

    feature_importances = pipeline.named_steps["regressor"].feature_importances_
    analyzer.feature_importances["pump_duration"] = dict(zip(feature_names, feature_importances))
    analyzer.pump_duration_model = pipeline

    print(f"Pump süresi tahmin modeli eğitildi. MAE: {mae:.4f}, R²: {r2:.4f}")
    return True


def train_price_prediction_model(analyzer, mint_addresses=None, test_size=0.2, random_state=42):
    """Fiyat tahmin modeli eğitir."""
    print("Fiyat tahmin modeli eğitiliyor...")

    features, _, _, future_prices = prepare_dataset(analyzer, mint_addresses)
    
    if not features or len(features) < 10:
        print("Eğitim için yeterli veri yok!")
        return False

    feature_names = list(features[0].keys())
    df_features = pd.DataFrame(features)
    df_labels = pd.Series(future_prices)
    
    df_features = df_features.fillna(0)
    df_labels = df_labels.fillna(df_labels.mean())

    X_train, X_test, y_train, y_test = train_test_split(
        df_features,
        df_labels,
        test_size=test_size,
        random_state=random_state,
    )

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        (
            "regressor",
            GradientBoostingRegressor(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=4,
                random_state=random_state,
            ),
        ),
    ])

    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)

    mae = mean_absolute_error(y_test, y_pred)
    mse = mean_squared_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    analyzer.model_metrics["price_prediction"]["mae"] = mae
    analyzer.model_metrics["price_prediction"]["mse"] = mse
    analyzer.model_metrics["price_prediction"]["r2"] = r2

    feature_importances = pipeline.named_steps["regressor"].feature_importances_
    analyzer.feature_importances["price_prediction"] = dict(zip(feature_names, feature_importances))
    analyzer.price_prediction_model = pipeline

    print(f"Fiyat tahmin modeli eğitildi. MAE: {mae:.4f}, R²: {r2:.4f}")
    return True


def train_ensemble_model(analyzer, mint_addresses=None, test_size=0.2, random_state=42):
    """Ensemble model eğitir (birden fazla modelin birleşimi)."""
    print("Ensemble modeli eğitiliyor...")

    features, pump_labels, _, _ = prepare_dataset(analyzer, mint_addresses)
    if len(features) < 20:
        print("Eğitim için yeterli veri yok!")
        return False

    df_features = pd.DataFrame(features)
    df_labels = pd.Series(pump_labels)
    df_features = df_features.fillna(0)

    X_train, X_test, y_train, y_test = train_test_split(
        df_features, df_labels, test_size=test_size, random_state=random_state
    )

    base_models = [
        (
            "gb",
            GradientBoostingClassifier(n_estimators=100, learning_rate=0.1, max_depth=4, random_state=random_state),
        ),
        ("rf", RandomForestClassifier(n_estimators=100, random_state=random_state)),
        ("ada", AdaBoostClassifier(n_estimators=50, random_state=random_state)),
        ("lr", LogisticRegression(C=1.0, random_state=random_state)),
    ]

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("ensemble", VotingClassifier(estimators=base_models, voting="soft")),
    ])

    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)

    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)

    analyzer.model_metrics["ensemble"] = {
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }

    analyzer.ensemble_model = pipeline
    print(f"Ensemble model eğitildi. F1 Skoru: {f1:.4f}")
    return True
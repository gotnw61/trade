# -*- coding: utf-8 -*-
import copy
from loguru import logger

from config import STRATEGY_PROFILES

class TradeStrategy:
    """
    Alım/satım stratejileri için temel sınıf
    """
    def __init__(self, name, settings=None):
        """
        Yeni bir strateji örneği oluştur
        
        Args:
            name (str): Strateji adı
            settings (dict, optional): Strateji ayarları
        """
        self.name = name
        
        # Ayarları varsayılan değerlerle başlat
        self.settings = {
            "sell_profit_targets": [
                {"profit": 20, "sell_percentage": 25},
                {"profit": 50, "sell_percentage": 25},
                {"profit": 100, "sell_percentage": 25},
                {"profit": 150, "sell_percentage": 25}
            ],
            "sell_stop_loss_levels": [
                {"loss": -5, "sell_percentage": 50},
                {"loss": -10, "sell_percentage": 50}
            ],
            "trailing_stop_loss": 5.0,
            "momentum_threshold": 5.0,
            "dip_buy_threshold": 15.0,
            "micro_pump_threshold": 3.0
        }
        
        # Eğer belirtilmişse ayarları güncelle
        if settings:
            self.settings.update(settings)
        
        logger.info(f"'{name}' stratejisi oluşturuldu")

    def should_buy(self, token_data):
        """
        Alım koşullarını kontrol eder
        
        Args:
            token_data (dict): Token verileri ve analizleri
            
        Returns:
            tuple: (Alım yapılmalı mı, Gerekçe)
        """
        reasons = []
        
        # Momentum tabanlı alım
        if token_data.get("momentum", 0) >= self.settings["momentum_threshold"]:
            reasons.append(f"Momentum: {token_data['momentum']:.2f}% >= {self.settings['momentum_threshold']}%")
        
        # Dip alımı
        if token_data.get("dip_percentage", 0) >= self.settings["dip_buy_threshold"]:
            reasons.append(f"Dip: {token_data['dip_percentage']:.2f}% >= {self.settings['dip_buy_threshold']}%")
        
        # Mikro pump alımı
        if token_data.get("micro_pump", 0) >= self.settings["micro_pump_threshold"]:
            reasons.append(f"Micro Pump: {token_data['micro_pump']:.2f}% >= {self.settings['micro_pump_threshold']}%")
        
        # Eğer en az bir neden varsa alım yapılmalı
        should_buy = len(reasons) > 0
        reason = ", ".join(reasons) if reasons else "Alım koşulları karşılanmadı"
        
        return should_buy, reason

    def should_sell(self, position_data):
        """
        Satım koşullarını kontrol eder
        
        Args:
            position_data (dict): Pozisyon verileri
            
        Returns:
            tuple: (Satım yapılmalı mı, Satım yüzdesi, Gerekçe)
        """
        price_change = position_data.get("price_change_percentage", 0)
        highest_price = position_data.get("highest_price", 0)
        current_price = position_data.get("current_price", 0)
        
        # Trailing stop loss kontrolü
        trailing_drop = 0
        if highest_price > 0 and current_price < highest_price:
            trailing_drop = ((highest_price - current_price) / highest_price) * 100
            
            if trailing_drop >= self.settings["trailing_stop_loss"]:
                return True, 100, f"Trailing Stop-Loss: {trailing_drop:.2f}% >= {self.settings['trailing_stop_loss']}%"
        
        # Kâr hedefleri kontrolü
        for target in sorted(self.settings["sell_profit_targets"], key=lambda x: x["profit"]):
            if price_change >= target["profit"]:
                return True, target["sell_percentage"], f"Kâr Hedefi: {price_change:.2f}% >= {target['profit']}%"
        
        # Zarar kesme kontrolü
        for stop in sorted(self.settings["sell_stop_loss_levels"], key=lambda x: x["loss"], reverse=True):
            if price_change <= stop["loss"]:
                return True, stop["sell_percentage"], f"Zarar Kesme: {price_change:.2f}% <= {stop['loss']}%"
        
        return False, 0, "Satım koşulları karşılanmadı"

    def calculate_position_size(self, available_balance, token_data, risk_level="normal"):
        """
        Pozisyon büyüklüğünü hesaplar
        
        Args:
            available_balance (float): Kullanılabilir bakiye
            token_data (dict): Token verileri
            risk_level (str): Risk seviyesi (low, normal, high)
            
        Returns:
            float: Pozisyon büyüklüğü (SOL)
        """
        # Risk katsayısı
        risk_multiplier = {
            "low": 0.7,
            "normal": 1.0,
            "high": 1.3
        }.get(risk_level, 1.0)
        
        # Varsayılan pozisyon büyüklüğü
        default_size = available_balance * 0.1  # Bakiyenin %10'u
        
        # Token verileri mevcut değilse varsayılan boyut
        if not token_data:
            return default_size * risk_multiplier
        
        # Volatilite faktörü
        volatility = token_data.get("volatility", 10)
        volatility_factor = max(0.5, min(1.5, 10 / volatility))  # Yüksek volatilite = küçük pozisyon
        
        # Likidite faktörü
        liquidity = token_data.get("liquidity_usd", 10000)
        liquidity_factor = min(1.0, liquidity / 50000)  # Düşük likidite = küçük pozisyon
        
        # Momentum faktörü
        momentum = token_data.get("momentum", 0)
        momentum_factor = 1.0 + (momentum / 100)  # Yüksek momentum = büyük pozisyon
        
        # Son pozisyon boyutu
        position_size = default_size * risk_multiplier * volatility_factor * liquidity_factor * momentum_factor
        
        # Minimum ve maksimum sınırlar
        min_size = available_balance * 0.01  # En az bakiyenin %1'i
        max_size = available_balance * 0.2   # En fazla bakiyenin %20'si
        
        return max(min_size, min(position_size, max_size))

    def copy(self):
        """
        Stratejinin bir kopyasını oluşturur
        
        Returns:
            TradeStrategy: Stratejinin kopyası
        """
        return TradeStrategy(self.name, copy.deepcopy(self.settings))

    def __str__(self):
        """
        Stratejiyi string olarak temsil eder
        
        Returns:
            str: Strateji bilgileri
        """
        return f"Strateji: {self.name}\n" + \
               f"TP Hedefleri: {self.settings['sell_profit_targets']}\n" + \
               f"SL Seviyeleri: {self.settings['sell_stop_loss_levels']}\n" + \
               f"Trailing Stop: {self.settings['trailing_stop_loss']}%"


class AgresifStrategy(TradeStrategy):
    """
    Agresif alım/satım stratejisi
    """
    def __init__(self, settings=None):
        """
        Agresif strateji örneği oluştur
        
        Args:
            settings (dict, optional): Özel ayarlar
        """
        # Agresif strateji ayarları
        agresif_settings = {
            "sell_profit_targets": [
                {"profit": 20, "sell_percentage": 30},
                {"profit": 50, "sell_percentage": 70},
                {"profit": 100, "sell_percentage": 100}
            ],
            "sell_stop_loss_levels": [
                {"loss": -5, "sell_percentage": 50},
                {"loss": -10, "sell_percentage": 100}
            ],
            "trailing_stop_loss": 3.0,
            "momentum_threshold": 3.0,
            "dip_buy_threshold": 10.0,
            "micro_pump_threshold": 2.0
        }
        
        # Özel ayarlar varsa güncelle
        if settings:
            agresif_settings.update(settings)
        
        # Üst sınıf yapıcısını çağır
        super().__init__("agresif", agresif_settings)
        
    def should_buy(self, token_data):
        """
        Agresif alım koşullarını kontrol eder
        
        Args:
            token_data (dict): Token verileri ve analizleri
            
        Returns:
            tuple: (Alım yapılmalı mı, Gerekçe)
        """
        # Düşük momentumda bile alım yap
        momentum_threshold = self.settings["momentum_threshold"]
        momentum = token_data.get("momentum", 0)
        
        micro_pump = token_data.get("micro_pump", 0)
        micro_pump_threshold = self.settings["micro_pump_threshold"]
        
        # Ya momentum ya da mikro pump koşulu sağlanırsa al
        should_buy = (momentum >= momentum_threshold) or (micro_pump >= micro_pump_threshold)
        reason = ""
        
        if momentum >= momentum_threshold:
            reason += f"Momentum: {momentum:.2f}% >= {momentum_threshold}%"
            
        if micro_pump >= micro_pump_threshold:
            reason += f"{', ' if reason else ''}Micro Pump: {micro_pump:.2f}% >= {micro_pump_threshold}%"
            
        if not should_buy:
            reason = "Alım koşulları karşılanmadı"
        
        return should_buy, reason


class DengeliStrategy(TradeStrategy):
    """
    Dengeli alım/satım stratejisi
    """
    def __init__(self, settings=None):
        """
        Dengeli strateji örneği oluştur
        
        Args:
            settings (dict, optional): Özel ayarlar
        """
        # Dengeli strateji ayarları
        dengeli_settings = {
            "sell_profit_targets": [
                {"profit": 10, "sell_percentage": 33},
                {"profit": 20, "sell_percentage": 33},
                {"profit": 50, "sell_percentage": 34}
            ],
            "sell_stop_loss_levels": [
                {"loss": -10, "sell_percentage": 50},
                {"loss": -20, "sell_percentage": 100}
            ],
            "trailing_stop_loss": 5.0,
            "momentum_threshold": 5.0,
            "dip_buy_threshold": 15.0,
            "micro_pump_threshold": 3.0
        }
        
        # Özel ayarlar varsa güncelle
        if settings:
            dengeli_settings.update(settings)
        
        # Üst sınıf yapıcısını çağır
        super().__init__("dengeli", dengeli_settings)


class MuhafazakarStrategy(TradeStrategy):
    """
    Muhafazakar alım/satım stratejisi
    """
    def __init__(self, settings=None):
        """
        Muhafazakar strateji örneği oluştur
        
        Args:
            settings (dict, optional): Özel ayarlar
        """
        # Muhafazakar strateji ayarları
        muhafazakar_settings = {
            "sell_profit_targets": [
                {"profit": 5, "sell_percentage": 50},
                {"profit": 10, "sell_percentage": 50}
            ],
            "sell_stop_loss_levels": [
                {"loss": -15, "sell_percentage": 50},
                {"loss": -25, "sell_percentage": 100}
            ],
            "trailing_stop_loss": 7.0,
            "momentum_threshold": 8.0,
            "dip_buy_threshold": 20.0,
            "micro_pump_threshold": 5.0
        }
        
        # Özel ayarlar varsa güncelle
        if settings:
            muhafazakar_settings.update(settings)
        
        # Üst sınıf yapıcısını çağır
        super().__init__("muhafazakar", muhafazakar_settings)
        
    def should_buy(self, token_data):
        """
        Muhafazakar alım koşullarını kontrol eder (daha sıkı koşullar)
        
        Args:
            token_data (dict): Token verileri ve analizleri
            
        Returns:
            tuple: (Alım yapılmalı mı, Gerekçe)
        """
        reasons = []
        
        # Momentumun yanında başka göstergeler de kontrol et
        momentum = token_data.get("momentum", 0)
        volatility = token_data.get("volatility", float('inf'))
        liquidity_usd = token_data.get("liquidity_usd", 0)
        
        # Momentum yeterince yüksek mi?
        if momentum >= self.settings["momentum_threshold"]:
            reasons.append(f"Momentum: {momentum:.2f}% >= {self.settings['momentum_threshold']}%")
            
            # Volatilite çok yüksek değil mi?
            if volatility <= 20:
                reasons.append(f"Uygun Volatilite: {volatility:.2f}% <= 20%")
            else:
                # Yüksek volatilite ile alım için momentum daha yüksek olmalı
                if momentum < self.settings["momentum_threshold"] * 1.5:
                    return False, "Yüksek volatilite ile alım için yetersiz momentum"
            
            # Likidite yeterli mi?
            if liquidity_usd >= 15000:
                reasons.append(f"Yeterli Likidite: ${liquidity_usd:.2f} >= $15,000")
            else:
                # Düşük likidite ile alım için momentum daha yüksek olmalı
                if momentum < self.settings["momentum_threshold"] * 2:
                    return False, "Düşük likidite ile alım için yetersiz momentum"
        
        # Sadece hem momentum hem de en az bir diğer ölçüt karşılanırsa alım yap
        should_buy = len(reasons) >= 2
        reason = ", ".join(reasons) if reasons else "Alım koşulları karşılanmadı"
        
        return should_buy, reason


def get_strategy_by_name(name, custom_settings=None):
    """
    İsimle strateji döndüren fabrika fonksiyonu
    
    Args:
        name (str): Strateji adı
        custom_settings (dict, optional): Özel ayarlar
        
    Returns:
        TradeStrategy: Strateji örneği
    """
    strategies = {
        "agresif": AgresifStrategy,
        "dengeli": DengeliStrategy,
        "muhafazakar": MuhafazakarStrategy
    }
    
    # İstenilen strateji mevcut mu?
    if name.lower() in strategies:
        # Özel ayarlar varsa kullan, yoksa profil ayarlarını al
        settings = custom_settings
        if not settings and name.lower() in STRATEGY_PROFILES:
            settings = STRATEGY_PROFILES[name.lower()]
            
        return strategies[name.lower()](settings)
    
    # Varsayılan strateji
    logger.warning(f"'{name}' stratejisi bulunamadı, varsayılan 'dengeli' stratejisi kullanılıyor")
    return DengeliStrategy()


def apply_strategy_profile(strategy_name):
    """
    Belirli bir strateji profilini uygular
    
    Args:
        strategy_name (str): Strateji profili adı
    
    Returns:
        dict: Güncellenmiş ticaret ayarları
    """
    try:
        # Strateji profilinin var olup olmadığını kontrol et
        if strategy_name not in STRATEGY_PROFILES:
            print(f"Uyarı: '{strategy_name}' stratejisi bulunamadı. Varsayılan strateji kullanılacak.")
            strategy_name = "dengeli"  # Varsayılan strateji
        
        # Seçilen strateji profilini al
        strategy_settings = STRATEGY_PROFILES[strategy_name]
        
        # Ticaret ayarlarını güncelle
        trade_settings.update(strategy_settings)
        
        print(f"✅ {strategy_name.capitalize()} strateji profili uygulandı.")
        
        return trade_settings
    
    except Exception as e:
        print(f"❌ Strateji profili uygulama hatası: {e}")
        return trade_settings
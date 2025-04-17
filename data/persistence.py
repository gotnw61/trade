# -*- coding: utf-8 -*-
import json
import os
import pickle
from datetime import datetime
from loguru import logger

from utils.logging_utils import log_to_file
from config import APP_ROOT

def save_to_file(data, filename, file_type='json', directory=None):
    """
    Veriyi bir dosyaya kaydeder
    
    Args:
        data: Kaydedilecek veri
        filename (str): Dosya adı
        file_type (str): Dosya tipi ('json' veya 'pickle')
        directory (str): Kaydedilecek dizin (belirtilmezse APP_ROOT kullanılır)
    
    Returns:
        bool: İşlem başarısı
    """
    try:
        # Dizin belirtilmemişse APP_ROOT kullan
        if directory is None:
            directory = APP_ROOT
        
        # Dizin yoksa oluştur
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            
        # Tam dosya yolu
        file_path = os.path.join(directory, filename)
        
        # Dosya tipine göre kaydet
        if file_type.lower() == 'json':
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
        elif file_type.lower() == 'pickle':
            with open(file_path, 'wb') as f:
                pickle.dump(data, f)
        else:
            log_to_file(f"❌ Bilinmeyen dosya tipi: {file_type}")
            return False
            
        logger.info(f"Veri başarıyla kaydedildi: {file_path}")
        return True
    except Exception as e:
        log_to_file(f"❌ Dosya kaydedilemedi: {e}")
        logger.error(f"Dosya kaydedilemedi: {e}")
        return False

def load_from_file(filename, file_type='json', directory=None, default=None):
    """
    Bir dosyadan veri yükler
    
    Args:
        filename (str): Dosya adı
        file_type (str): Dosya tipi ('json' veya 'pickle')
        directory (str): Yüklenecek dizin (belirtilmezse APP_ROOT kullanılır)
        default: Dosya bulunamazsa döndürülecek varsayılan değer
    
    Returns:
        Yüklenen veri veya varsayılan değer
    """
    try:
        # Dizin belirtilmemişse APP_ROOT kullan
        if directory is None:
            directory = APP_ROOT
            
        # Tam dosya yolu
        file_path = os.path.join(directory, filename)
        
        # Dosya var mı kontrol et
        if not os.path.exists(file_path):
            logger.warning(f"Dosya bulunamadı: {file_path}")
            return default
            
        # Dosya tipine göre yükle
        if file_type.lower() == 'json':
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        elif file_type.lower() == 'pickle':
            with open(file_path, 'rb') as f:
                data = pickle.load(f)
        else:
            log_to_file(f"❌ Bilinmeyen dosya tipi: {file_type}")
            return default
            
        logger.info(f"Veri başarıyla yüklendi: {file_path}")
        return data
    except Exception as e:
        log_to_file(f"❌ Dosya yüklenemedi: {e}")
        logger.error(f"Dosya yüklenemedi: {e}")
        return default
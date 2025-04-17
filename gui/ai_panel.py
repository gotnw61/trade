# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from config import trade_settings

def create_ai_panel(gui):
    """
    AI panelini oluşturur ve gerekli widget'ları ekler.
    
    Args:
        gui (TradeBotGUI): Ana GUI sınıfı örneği
    """
    frame = gui.ai_frame

    # AI Modelleri Yönetimi
    models_frame = ttk.LabelFrame(frame, text="AI Model Yönetimi")
    models_frame.pack(fill=tk.X, padx=10, pady=10)

    # Model Eğitimi Butonu
    train_models_btn = ttk.Button(
        models_frame, 
        text="AI Modellerini Eğit", 
        command=gui.train_ai_models
    )
    train_models_btn.pack(side=tk.LEFT, padx=5, pady=5)

    # Model Yükleme Butonu
    load_models_btn = ttk.Button(
        models_frame, 
        text="AI Modellerini Yükle", 
        command=gui.load_ai_models
    )
    load_models_btn.pack(side=tk.LEFT, padx=5, pady=5)

    # Model Kaydetme Butonu
    save_models_btn = ttk.Button(
        models_frame, 
        text="AI Modellerini Kaydet", 
        command=gui.save_ai_models
    )
    save_models_btn.pack(side=tk.LEFT, padx=5, pady=5)

    # Model Performans Raporu
    performance_frame = ttk.LabelFrame(frame, text="Model Performans Raporu")
    performance_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Performans grafiği için figure ve canvas
    gui.ai_figure = plt.Figure(figsize=(6, 4), dpi=100)
    gui.ai_ax = gui.ai_figure.add_subplot(111)
    gui.ai_canvas = FigureCanvasTkAgg(gui.ai_figure, performance_frame)
    gui.ai_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Performans Raporu Butonu
    show_performance_btn = ttk.Button(
        performance_frame, 
        text="Performans Raporunu Göster", 
        command=gui.show_ai_performance
    )
    show_performance_btn.pack(side=tk.BOTTOM, padx=5, pady=5)

    # AI Özellikleri Kontrol Çerçevesi
    ai_features_frame = ttk.LabelFrame(frame, text="AI Özellikleri")
    ai_features_frame.pack(fill=tk.X, padx=10, pady=10)

    # AI Özelliklerini Açma/Kapatma Kontrolleri
    gui.pump_detection_var = tk.BooleanVar(master=frame, value=trade_settings.get("ai_enabled", False))
    pump_detection_check = ttk.Checkbutton(
        ai_features_frame, 
        text="Pump Algılama", 
        variable=gui.pump_detection_var,
        command=gui.toggle_pump_detection
    )
    pump_detection_check.pack(anchor=tk.W, padx=5, pady=2)

    gui.duration_prediction_var = tk.BooleanVar(master=frame, value=trade_settings.get("ai_pump_duration_prediction_enabled", False))
    duration_prediction_check = ttk.Checkbutton(
        ai_features_frame, 
        text="Pump Süresi Tahmini", 
        variable=gui.duration_prediction_var,
        command=gui.toggle_pump_duration_prediction
    )
    duration_prediction_check.pack(anchor=tk.W, padx=5, pady=2)

    # AI Güven Eşiği
    confidence_frame = ttk.Frame(ai_features_frame)
    confidence_frame.pack(fill=tk.X, padx=5, pady=2)

    ttk.Label(confidence_frame, text="AI Güven Eşiği:").pack(side=tk.LEFT, padx=5)

    gui.confidence_var = tk.StringVar(master=frame, value=str(trade_settings.get("ai_confidence_threshold", 0.7)))
    confidence_entry = ttk.Entry(confidence_frame, width=10, textvariable=gui.confidence_var)
    confidence_entry.pack(side=tk.LEFT, padx=5)

    set_confidence_btn = ttk.Button(
        confidence_frame, 
        text="Güven Eşiğini Ayarla", 
        command=gui.set_ai_confidence_threshold
    )
    set_confidence_btn.pack(side=tk.LEFT, padx=5)
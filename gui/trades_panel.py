# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from utils import format_price

def create_trades_panel(gui):
    """İşlemler panelini oluşturur"""
    frame = gui.trades_frame

    # Sol panel - Geçmiş işlemler
    history_frame = ttk.LabelFrame(frame, text="Geçmiş İşlemler")
    history_frame.pack(
        fill=tk.BOTH,
        expand=True,
        side=tk.LEFT,
        padx=10,
        pady=10)

    # Tablo ve kaydırma çubuğu
    table_frame = ttk.Frame(history_frame)
    table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    gui.history_table = ttk.Treeview(table_frame,
                                  columns=("date", "type", "token", "price", "amount", "profit"))
    gui.history_table.heading("#0", text="Mint Adresi")
    gui.history_table.heading("date", text="Tarih")
    gui.history_table.heading("type", text="İşlem")
    gui.history_table.heading("token", text="Token")
    gui.history_table.heading("price", text="Fiyat")
    gui.history_table.heading("amount", text="Miktar")
    gui.history_table.heading("profit", text="Kâr/Zarar")

    # Sütun genişlikleri
    gui.history_table.column("#0", width=150)
    gui.history_table.column("date", width=130)
    gui.history_table.column("type", width=70)
    gui.history_table.column("token", width=80)
    gui.history_table.column("price", width=100)
    gui.history_table.column("amount", width=80)
    gui.history_table.column("profit", width=100)

    gui.history_table.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

    # Dikey scrollbar
    scrollbar = ttk.Scrollbar(
        table_frame,
        orient=tk.VERTICAL,
        command=gui.history_table.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    gui.history_table.configure(yscrollcommand=scrollbar.set)

    # Butonlar
    history_buttons_frame = ttk.Frame(history_frame)
    history_buttons_frame.pack(fill=tk.X, padx=5, pady=5)

    gui.refresh_history_btn = ttk.Button(history_buttons_frame, text="Geçmişi Yenile",
                                      command=gui.refresh_trade_history)
    gui.refresh_history_btn.pack(side=tk.LEFT, padx=5, pady=5)

    gui.export_history_btn = ttk.Button(history_buttons_frame, text="Geçmişi Dışa Aktar",
                                     command=gui.export_trade_history)
    gui.export_history_btn.pack(side=tk.LEFT, padx=5, pady=5)

    # Sağ panel - Grafik ve analiz
    chart_frame = ttk.LabelFrame(frame, text="İşlem Analizi")
    chart_frame.pack(
        fill=tk.BOTH,
        expand=True,
        side=tk.RIGHT,
        padx=10,
        pady=10)

    # Grafik alanı
    gui.figure = plt.Figure(figsize=(6, 4), dpi=100)
    gui.ax = gui.figure.add_subplot(111)
    gui.canvas = FigureCanvasTkAgg(gui.figure, chart_frame)
    gui.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Özet istatistikler
    stats_frame = ttk.Frame(chart_frame)
    stats_frame.pack(fill=tk.X, padx=5, pady=5)

    # Toplam işlem
    ttk.Label(
        stats_frame,
        text="Toplam İşlem:").grid(
        row=0,
        column=0,
        sticky=tk.W,
        padx=5,
        pady=2)
    gui.total_trades_label = ttk.Label(stats_frame, text="0")
    gui.total_trades_label.grid(
        row=0, column=1, sticky=tk.W, padx=5, pady=2)

    # Başarılı işlemler
    ttk.Label(
        stats_frame,
        text="Başarılı İşlemler:").grid(
        row=1,
        column=0,
        sticky=tk.W,
        padx=5,
        pady=2)
    gui.profitable_trades_label = ttk.Label(stats_frame, text="0")
    gui.profitable_trades_label.grid(
        row=1, column=1, sticky=tk.W, padx=5, pady=2)

    # Başarı oranı
    ttk.Label(
        stats_frame,
        text="Başarı Oranı:").grid(
        row=2,
        column=0,
        sticky=tk.W,
        padx=5,
        pady=2)
    gui.success_rate_label = ttk.Label(stats_frame, text="0%")
    gui.success_rate_label.grid(
        row=2, column=1, sticky=tk.W, padx=5, pady=2)

    # Toplam kâr/zarar
    ttk.Label(stats_frame, text="Toplam Kâr/Zarar:").grid(row=0,
                                                      column=2, sticky=tk.W, padx=5, pady=2)
    gui.total_profit_label = ttk.Label(stats_frame, text="0.00 SOL")
    gui.total_profit_label.grid(
        row=0, column=3, sticky=tk.W, padx=5, pady=2)

    # Ortalama kâr
    ttk.Label(
        stats_frame,
        text="Ortalama Kâr:").grid(
        row=1,
        column=2,
        sticky=tk.W,
        padx=5,
        pady=2)
    gui.avg_profit_label = ttk.Label(stats_frame, text="0.00 SOL")
    gui.avg_profit_label.grid(
        row=1, column=3, sticky=tk.W, padx=5, pady=2)

    # Ortalama zarar
    ttk.Label(
        stats_frame,
        text="Ortalama Zarar:").grid(
        row=2,
        column=2,
        sticky=tk.W,
        padx=5,
        pady=2)
    gui.avg_loss_label = ttk.Label(stats_frame, text="0.00 SOL")
    gui.avg_loss_label.grid(row=2, column=3, sticky=tk.W, padx=5, pady=2)

    # İşlem geçmişini güncelle
    gui.refresh_trade_history()
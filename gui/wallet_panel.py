# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from gotnw_tradebot.utils import format_price

def create_wallet_panel(gui):
    """Cüzdan panelini oluşturur"""
    frame = gui.wallet_frame

    # Cüzdan yönetimi
    wallet_mgmt_frame = ttk.LabelFrame(frame, text="Cüzdan Yönetimi")
    wallet_mgmt_frame.pack(fill=tk.X, padx=10, pady=10)

    # Cüzdan bağlama
    connect_frame = ttk.Frame(wallet_mgmt_frame)
    connect_frame.pack(fill=tk.X, padx=5, pady=5)

    ttk.Label(
        connect_frame,
        text="Özel Anahtar:").pack(
        side=tk.LEFT,
        padx=5,
        pady=5)

    gui.private_key_entry = ttk.Entry(connect_frame, width=70, show="*")
    gui.private_key_entry.pack(side=tk.LEFT, padx=5, pady=5)

    gui.connect_wallet_btn = ttk.Button(connect_frame, text="Cüzdan Bağla",
                                     command=gui.connect_wallet)
    gui.connect_wallet_btn.pack(side=tk.LEFT, padx=5, pady=5)

    # Bağlı cüzdanlar listesi
    wallets_frame = ttk.Frame(wallet_mgmt_frame)
    wallets_frame.pack(fill=tk.X, padx=5, pady=5)

    ttk.Label(
        wallets_frame,
        text="Bağlı Cüzdanlar:").pack(
        side=tk.LEFT,
        padx=5,
        pady=5)

    gui.wallets_combo = ttk.Combobox(
        wallets_frame, width=60, state="readonly")
    gui.wallets_combo.pack(side=tk.LEFT, padx=5, pady=5)

    gui.switch_wallet_btn = ttk.Button(wallets_frame, text="Cüzdan Değiştir",
                                    command=gui.switch_wallet)
    gui.switch_wallet_btn.pack(side=tk.LEFT, padx=5, pady=5)

    # Token işlemleri
    token_frame = ttk.LabelFrame(frame, text="Token İşlemleri")
    token_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Token izleme
    monitor_frame = ttk.Frame(token_frame)
    monitor_frame.pack(fill=tk.X, padx=5, pady=5)

    ttk.Label(
        monitor_frame,
        text="Mint Adresi:").pack(
        side=tk.LEFT,
        padx=5,
        pady=5)

    gui.token_entry = ttk.Entry(monitor_frame, width=60)
    gui.token_entry.pack(side=tk.LEFT, padx=5, pady=5)

    gui.add_token_btn = ttk.Button(monitor_frame, text="Token Ekle",
                                command=gui.add_token_to_watch)
    gui.add_token_btn.pack(side=tk.LEFT, padx=5, pady=5)

    # İzlenen tokenler tablosu
    watched_frame = ttk.Frame(token_frame)
    watched_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    gui.watched_tokens_table = ttk.Treeview(watched_frame,
                                         columns=("token", "price", "liquidity", "volume", "added"))
    gui.watched_tokens_table.heading("#0", text="Mint Adresi")
    gui.watched_tokens_table.heading("token", text="Token")
    gui.watched_tokens_table.heading("price", text="Fiyat")
    gui.watched_tokens_table.heading("liquidity", text="Likidite")
    gui.watched_tokens_table.heading("volume", text="Hacim")
    gui.watched_tokens_table.heading("added", text="Eklenme Zamanı")

    # Sütun genişlikleri
    gui.watched_tokens_table.column("#0", width=150)
    gui.watched_tokens_table.column("token", width=80)
    gui.watched_tokens_table.column("price", width=100)
    gui.watched_tokens_table.column("liquidity", width=100)
    gui.watched_tokens_table.column("volume", width=100)
    gui.watched_tokens_table.column("added", width=130)

    gui.watched_tokens_table.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

    # Dikey scrollbar
    scrollbar = ttk.Scrollbar(
        watched_frame,
        orient=tk.VERTICAL,
        command=gui.watched_tokens_table.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    gui.watched_tokens_table.configure(yscrollcommand=scrollbar.set)

    # Token butonları
    token_buttons_frame = ttk.Frame(token_frame)
    token_buttons_frame.pack(fill=tk.X, padx=5, pady=5)

    gui.refresh_tokens_btn = ttk.Button(token_buttons_frame, text="Tokenleri Yenile",
                                     command=gui.refresh_watched_tokens)
    gui.refresh_tokens_btn.pack(side=tk.LEFT, padx=5, pady=5)

    gui.remove_token_btn = ttk.Button(token_buttons_frame, text="Seçili Tokeni Kaldır",
                                   command=gui.remove_watched_token)
    gui.remove_token_btn.pack(side=tk.LEFT, padx=5, pady=5)

    gui.buy_token_btn = ttk.Button(token_buttons_frame, text="Seçili Tokeni Satın Al",
                                command=gui.buy_selected_token)
    gui.buy_token_btn.pack(side=tk.LEFT, padx=5, pady=5)

    # Token analiz butonu
    gui.analyze_token_btn = ttk.Button(token_buttons_frame, text="Seçili Tokeni Analiz Et",
                                    command=gui.analyze_selected_token)
    gui.analyze_token_btn.pack(side=tk.LEFT, padx=5, pady=5)
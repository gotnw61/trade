# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from gotnw_tradebot.utils import format_price, animated_text
from gotnw_tradebot.config import trade_settings

def create_dashboard(gui):
    """Kontrol paneli içeriğini oluşturur"""
    frame = gui.dashboard_frame

    # Trade settings'ten değerleri al, varsayılan değerler belirt
    autobuy_value = trade_settings.get("autobuy_enabled", False)
    autosell_value = trade_settings.get("autosell_enabled", False)
    simulation_value = trade_settings.get("simulation_mode", False)

    # Tkinter değişkenlerini oluştur
    gui.autobuy_var = tk.BooleanVar(master=frame, value=autobuy_value)
    gui.autosell_var = tk.BooleanVar(master=frame, value=autosell_value)
    gui.simulation_var = tk.BooleanVar(master=frame, value=simulation_value)

    # Üst kısım - Durum ve kontroller
    top_frame = ttk.Frame(frame)
    top_frame.pack(fill=tk.X, padx=10, pady=10)

    # Sol panel - Durum bilgileri
    status_frame = ttk.LabelFrame(top_frame, text="Bot Durumu")
    status_frame.pack(
        side=tk.LEFT,
        fill=tk.BOTH,
        expand=True,
        padx=5,
        pady=5)

    # Cüzdan bilgisi
    wallet_frame = ttk.Frame(status_frame)
    wallet_frame.pack(fill=tk.X, padx=5, pady=5)

    ttk.Label(wallet_frame, text="Cüzdan:").pack(side=tk.LEFT)
    gui.wallet_address_label = ttk.Label(wallet_frame, text="Bağlı değil")
    gui.wallet_address_label.pack(side=tk.LEFT, padx=5)

    # Bakiye bilgisi
    balance_frame = ttk.Frame(status_frame)
    balance_frame.pack(fill=tk.X, padx=5, pady=5)

    ttk.Label(balance_frame, text="SOL Bakiye:").pack(side=tk.LEFT)
    gui.balance_label = ttk.Label(balance_frame, text="0.00")
    gui.balance_label.pack(side=tk.LEFT, padx=5)

    ttk.Label(
        balance_frame,
        text="USD Değeri:").pack(
        side=tk.LEFT,
        padx=10)
    gui.usd_balance_label = ttk.Label(balance_frame, text="$0.00")
    gui.usd_balance_label.pack(side=tk.LEFT, padx=5)

    # SOL fiyatı
    sol_frame = ttk.Frame(status_frame)
    sol_frame.pack(fill=tk.X, padx=5, pady=5)

    ttk.Label(sol_frame, text="SOL Fiyatı:").pack(side=tk.LEFT)
    gui.sol_price_label = ttk.Label(sol_frame, text="$0.00")
    gui.sol_price_label.pack(side=tk.LEFT, padx=5)

    # Bot durumu
    bot_status_frame = ttk.Frame(status_frame)
    bot_status_frame.pack(fill=tk.X, padx=5, pady=5)

    ttk.Label(bot_status_frame, text="Bot Durumu:").pack(side=tk.LEFT)
    gui.bot_status_label = ttk.Label(
        bot_status_frame, text="Durduruldu", foreground="red")
    gui.bot_status_label.pack(side=tk.LEFT, padx=5)

    # Strateji
    strategy_frame = ttk.Frame(status_frame)
    strategy_frame.pack(fill=tk.X, padx=5, pady=5)

    ttk.Label(strategy_frame, text="Aktif Strateji:").pack(side=tk.LEFT)
    from gotnw_tradebot.config import current_strategy
    gui.strategy_label = ttk.Label(
        strategy_frame, text=current_strategy.capitalize())
    gui.strategy_label.pack(side=tk.LEFT, padx=5)

    # Mod bilgisi
    mode_frame = ttk.Frame(status_frame)
    mode_frame.pack(fill=tk.X, padx=5, pady=5)

    ttk.Label(mode_frame, text="Mod:").pack(side=tk.LEFT)
    gui.mode_label = ttk.Label(
        mode_frame,
        text="Simülasyon" if trade_settings["simulation_mode"] else "Gerçek")
    gui.mode_label.pack(side=tk.LEFT, padx=5)

    # Sağ panel - Hızlı kontroller
    controls_frame = ttk.LabelFrame(top_frame, text="Kontroller")
    controls_frame.pack(
        side=tk.RIGHT,
        fill=tk.BOTH,
        expand=True,
        padx=5,
        pady=5)

    # Bot başlat/durdur
    bot_control_frame = ttk.Frame(controls_frame)
    bot_control_frame.pack(fill=tk.X, padx=5, pady=5)

    gui.start_bot_btn = ttk.Button(
        bot_control_frame,
        text="Botu Başlat",
        command=gui.start_bot)
    gui.start_bot_btn.pack(side=tk.LEFT, padx=5, pady=5)

    gui.stop_bot_btn = ttk.Button(
        bot_control_frame,
        text="Botu Durdur",
        command=gui.stop_bot,
        state=tk.DISABLED)
    gui.stop_bot_btn.pack(side=tk.LEFT, padx=5, pady=5)

    # Otomatik alım/satım kontrolleri
    auto_frame = ttk.Frame(controls_frame)
    auto_frame.pack(fill=tk.X, padx=5, pady=5)

    gui.autobuy_check = ttk.Checkbutton(auto_frame, text="Otomatik Alım",
                                     variable=gui.autobuy_var, command=gui.toggle_autobuy)
    gui.autobuy_check.pack(side=tk.LEFT, padx=5, pady=5)

    gui.autosell_check = ttk.Checkbutton(auto_frame, text="Otomatik Satım",
                                      variable=gui.autosell_var, command=gui.toggle_autosell)
    gui.autosell_check.pack(side=tk.LEFT, padx=5, pady=5)

    # Simülasyon modu kontrolü
    sim_frame = ttk.Frame(controls_frame)
    sim_frame.pack(fill=tk.X, padx=5, pady=5)

    gui.simulation_check = ttk.Checkbutton(sim_frame, text="Simülasyon Modu",
                                        variable=gui.simulation_var, command=gui.toggle_simulation)
    gui.simulation_check.pack(side=tk.LEFT, padx=5, pady=5)

    # Manuel işlem butonları
    manual_frame = ttk.Frame(controls_frame)
    manual_frame.pack(fill=tk.X, padx=5, pady=5)

    gui.manual_buy_btn = ttk.Button(
        manual_frame,
        text="Manuel Alım",
        command=gui.show_manual_buy_dialog)
    gui.manual_buy_btn.pack(side=tk.LEFT, padx=5, pady=5)

    gui.manual_sell_btn = ttk.Button(
        manual_frame,
        text="Manuel Satım",
        command=gui.show_manual_sell_dialog)
    gui.manual_sell_btn.pack(side=tk.LEFT, padx=5, pady=5)

    # Durum kaydet/yükle butonları
    state_frame = ttk.Frame(controls_frame)
    state_frame.pack(fill=tk.X, padx=5, pady=5)

    gui.save_state_btn = ttk.Button(
        state_frame,
        text="Durumu Kaydet",
        command=gui.save_bot_state)
    gui.save_state_btn.pack(side=tk.LEFT, padx=5, pady=5)

    gui.load_state_btn = ttk.Button(
        state_frame,
        text="Durumu Yükle",
        command=gui.load_bot_state)
    gui.load_state_btn.pack(side=tk.LEFT, padx=5, pady=5)

    # Alt kısım - Mevcut pozisyonlar ve log
    bottom_frame = ttk.Frame(frame)
    bottom_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    # Mevcut pozisyonlar tablosu
    positions_frame = ttk.LabelFrame(
        bottom_frame, text="Mevcut Pozisyonlar")
    positions_frame.pack(
        fill=tk.BOTH,
        expand=True,
        side=tk.LEFT,
        padx=5,
        pady=5)

    # Tablo ve kaydırma çubuğu
    table_frame = ttk.Frame(positions_frame)
    table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    gui.positions_table = ttk.Treeview(
        table_frame,
        columns=(
            "token",
            "buy_price",
            "current_price",
            "amount",
            "profit"))
    gui.positions_table.heading("#0", text="Mint Adresi")
    gui.positions_table.heading("token", text="Token")
    gui.positions_table.heading("buy_price", text="Alım Fiyatı")
    gui.positions_table.heading("current_price", text="Güncel Fiyat")
    gui.positions_table.heading("amount", text="Miktar (SOL)")
    gui.positions_table.heading("profit", text="Kâr/Zarar")

    # Sütun genişlikleri
    gui.positions_table.column("#0", width=150)
    gui.positions_table.column("token", width=80)
    gui.positions_table.column("buy_price", width=100)
    gui.positions_table.column("current_price", width=100)
    gui.positions_table.column("amount", width=100)
    gui.positions_table.column("profit", width=100)

    gui.positions_table.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

    # Dikey scrollbar
    scrollbar = ttk.Scrollbar(
        table_frame,
        orient=tk.VERTICAL,
        command=gui.positions_table.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    gui.positions_table.configure(yscrollcommand=scrollbar.set)

    # Pozisyon işlem butonları
    pos_buttons_frame = ttk.Frame(positions_frame)
    pos_buttons_frame.pack(fill=tk.X, padx=5, pady=5)

    gui.close_pos_btn = ttk.Button(positions_frame, text="Seçili Pozisyonu Kapat",
                                command=gui.close_selected_position)
    gui.close_pos_btn.pack(side=tk.LEFT, padx=5, pady=5)

    gui.refresh_pos_btn = ttk.Button(positions_frame, text="Pozisyonları Yenile",
                                  command=gui.refresh_positions)
    gui.refresh_pos_btn.pack(side=tk.LEFT, padx=5, pady=5)

    # Log alanı
    log_frame = ttk.LabelFrame(bottom_frame, text="Log")
    log_frame.pack(
        fill=tk.BOTH,
        expand=True,
        side=tk.RIGHT,
        padx=5,
        pady=5)

    from tkinter import scrolledtext
    gui.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD)
    gui.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Log butonları
    log_buttons_frame = ttk.Frame(log_frame)
    log_buttons_frame.pack(fill=tk.X, padx=5, pady=5)

    gui.clear_log_btn = ttk.Button(log_buttons_frame, text="Logu Temizle",
                                command=lambda: gui.log_text.delete(1.0, tk.END))
    gui.clear_log_btn.pack(side=tk.LEFT, padx=5, pady=5)
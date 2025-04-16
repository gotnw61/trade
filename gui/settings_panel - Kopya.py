# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, messagebox
from gotnw_tradebot.config import trade_settings, STRATEGY_PROFILES, current_strategy


def create_settings_panel(gui):
    """Ayarlar panelini oluşturur"""
    frame = gui.settings_frame

    # Sekmeli ayarlar
    settings_notebook = ttk.Notebook(frame)
    settings_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Temel ayarlar
    basic_settings_frame = ttk.Frame(settings_notebook)

    # TP/SL ayarları
    trading_settings_frame = ttk.Frame(settings_notebook)

    # İşlem ayarları
    trade_behavior_frame = ttk.Frame(settings_notebook)

    # Gelişmiş ayarlar
    advanced_settings_frame = ttk.Frame(settings_notebook)

    settings_notebook.add(basic_settings_frame, text="Temel Ayarlar")
    settings_notebook.add(trading_settings_frame, text="TP/SL Ayarları")
    settings_notebook.add(trade_behavior_frame, text="İşlem Ayarları")
    settings_notebook.add(advanced_settings_frame, text="Gelişmiş Ayarlar")

    # Temel ayarlar içeriği
    create_basic_settings(gui, basic_settings_frame)

    # TP/SL ayarları içeriği
    create_tpsl_settings(gui, trading_settings_frame)

    # İşlem ayarları içeriği
    create_trade_behavior_settings(gui, trade_behavior_frame)

    # Gelişmiş ayarlar içeriği
    create_advanced_settings(gui, advanced_settings_frame)

    # Ayarları kaydet butonu
    save_frame = ttk.Frame(frame)
    save_frame.pack(fill=tk.X, padx=10, pady=10)

    gui.save_settings_btn = ttk.Button(
        save_frame,
        text="Ayarları Kaydet",
        command=gui.save_settings
    )
    gui.save_settings_btn.pack(side=tk.RIGHT, padx=5, pady=5)


def create_basic_settings(gui, frame):
    """Temel ayarlar sekmesini oluşturur"""
    # Ticaret ayarları
    trade_frame = ttk.LabelFrame(frame, text="Ticaret Ayarları")
    trade_frame.pack(fill=tk.X, padx=10, pady=10)

    # Alım miktarı
    buy_frame = ttk.Frame(trade_frame)
    buy_frame.pack(fill=tk.X, padx=5, pady=5)

    ttk.Label(
        buy_frame,
        text="Alım Miktarı (SOL):"
    ).grid(
        row=0,
        column=0,
        sticky=tk.W,
        padx=5,
        pady=2
    )

    # Tüm değişkenlere master parametresini ekle
    gui.buy_amount_var = tk.StringVar(master=frame, value=str(trade_settings.get("buy_amount_sol", 0.2)))
    gui.min_liquidity_var = tk.StringVar(master=frame, value=str(trade_settings.get("min_liquidity_usd", 5000)))
    gui.max_positions_var = tk.StringVar(master=frame, value=str(trade_settings.get("max_positions", 5)))
    gui.min_balance_var = tk.StringVar(master=frame, value=str(trade_settings.get("min_balance_sol", 0.005)))
    gui.max_loss_var = tk.StringVar(master=frame, value=str(trade_settings.get("max_portfolio_loss", 30)))

    gui.buy_amount_entry = ttk.Entry(
        buy_frame,
        width=10,
        textvariable=gui.buy_amount_var
    )
    gui.buy_amount_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)

    # Minimum likidite
    ttk.Label(
        buy_frame,
        text="Minimum Likidite (USD):"
    ).grid(
        row=1,
        column=0,
        sticky=tk.W,
        padx=5,
        pady=2
    )

    gui.min_liquidity_entry = ttk.Entry(
        buy_frame,
        width=10,
        textvariable=gui.min_liquidity_var
    )
    gui.min_liquidity_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)

    # Maksimum pozisyon sayısı
    ttk.Label(
        buy_frame,
        text="Maksimum Pozisyon Sayısı:"
    ).grid(
        row=2,
        column=0,
        sticky=tk.W,
        padx=5,
        pady=2
    )

    gui.max_positions_entry = ttk.Entry(
        buy_frame,
        width=10,
        textvariable=gui.max_positions_var
    )
    gui.max_positions_entry.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)

    # Minimum bakiye
    ttk.Label(
        buy_frame,
        text="Minimum Bakiye (SOL):"
    ).grid(
        row=3,
        column=0,
        sticky=tk.W,
        padx=5,
        pady=2
    )

    gui.min_balance_entry = ttk.Entry(
        buy_frame,
        width=10,
        textvariable=gui.min_balance_var
    )
    gui.min_balance_entry.grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)

    # Maksimum portföy kaybı
    ttk.Label(
        buy_frame,
        text="Maksimum Portföy Kaybı (%):"
    ).grid(
        row=4,
        column=0,
        sticky=tk.W,
        padx=5,
        pady=2
    )

    gui.max_loss_entry = ttk.Entry(
        buy_frame,
        width=10,
        textvariable=gui.max_loss_var
    )
    gui.max_loss_entry.grid(row=4, column=1, sticky=tk.W, padx=5, pady=2)

    # Strateji profilleri
    strategy_frame = ttk.LabelFrame(frame, text="Strateji Profili")
    strategy_frame.pack(fill=tk.X, padx=10, pady=10)

    gui.strategy_var = tk.StringVar(master=frame, value=current_strategy)

    ttk.Radiobutton(
        strategy_frame,
        text="Agresif",
        value="agresif",
        variable=gui.strategy_var,
        command=gui.update_strategy
    ).pack(anchor=tk.W, padx=5, pady=2)

    ttk.Radiobutton(
        strategy_frame,
        text="Dengeli",
        value="dengeli",
        variable=gui.strategy_var,
        command=gui.update_strategy
    ).pack(anchor=tk.W, padx=5, pady=2)

    ttk.Radiobutton(
        strategy_frame,
        text="Muhafazakar",
        value="muhafazakar",
        variable=gui.strategy_var,
        command=gui.update_strategy
    ).pack(anchor=tk.W, padx=5, pady=2)


def create_tpsl_settings(gui, frame):
    """TP/SL ayarları sekmesini oluşturur"""
    # TP ayarları
    tp_frame = ttk.LabelFrame(frame, text="Kâr Alma (Take Profit) Seviyeleri")
    tp_frame.pack(fill=tk.X, padx=10, pady=10)

    # TP listesi için tablo
    tp_table_frame = ttk.Frame(tp_frame)
    tp_table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    gui.tp_table = ttk.Treeview(
        tp_table_frame,
        columns=("profit", "percentage"),
        height=4
    )
    gui.tp_table.heading("#0", text="#")
    gui.tp_table.heading("profit", text="Kâr (%)")
    gui.tp_table.heading("percentage", text="Satış Yüzdesi (%)")

    gui.tp_table.column("#0", width=50)
    gui.tp_table.column("profit", width=100)
    gui.tp_table.column("percentage", width=100)

    gui.tp_table.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

    # Ekle/Düzenle/Sil butonları
    tp_buttons_frame = ttk.Frame(tp_frame)
    tp_buttons_frame.pack(fill=tk.X, padx=5, pady=5)

    gui.add_tp_btn = ttk.Button(
        tp_buttons_frame,
        text="Ekle",
        command=gui.add_tp_level
    )
    gui.add_tp_btn.pack(side=tk.LEFT, padx=5, pady=5)

    gui.edit_tp_btn = ttk.Button(
        tp_buttons_frame,
        text="Düzenle",
        command=gui.edit_tp_level
    )
    gui.edit_tp_btn.pack(side=tk.LEFT, padx=5, pady=5)

    gui.delete_tp_btn = ttk.Button(
        tp_buttons_frame,
        text="Sil",
        command=gui.delete_tp_level
    )
    gui.delete_tp_btn.pack(side=tk.LEFT, padx=5, pady=5)

    # SL ayarları
    sl_frame = ttk.LabelFrame(frame, text="Zarar Kesme (Stop Loss) Seviyeleri")
    sl_frame.pack(fill=tk.X, padx=10, pady=10)

    # SL listesi için tablo
    sl_table_frame = ttk.Frame(sl_frame)
    sl_table_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    gui.sl_table = ttk.Treeview(
        sl_table_frame,
        columns=("loss", "percentage"),
        height=4
    )
    gui.sl_table.heading("#0", text="#")
    gui.sl_table.heading("loss", text="Zarar (%)")
    gui.sl_table.heading("percentage", text="Satış Yüzdesi (%)")

    gui.sl_table.column("#0", width=50)
    gui.sl_table.column("loss", width=100)
    gui.sl_table.column("percentage", width=100)

    gui.sl_table.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

    # Ekle/Düzenle/Sil butonları
    sl_buttons_frame = ttk.Frame(sl_frame)
    sl_buttons_frame.pack(fill=tk.X, padx=5, pady=5)

    gui.add_sl_btn = ttk.Button(
        sl_buttons_frame,
        text="Ekle",
        command=gui.add_sl_level
    )
    gui.add_sl_btn.pack(side=tk.LEFT, padx=5, pady=5)

    gui.edit_sl_btn = ttk.Button(
        sl_buttons_frame,
        text="Düzenle",
        command=gui.edit_sl_level
    )
    gui.edit_sl_btn.pack(side=tk.LEFT, padx=5, pady=5)

    gui.delete_sl_btn = ttk.Button(
        sl_buttons_frame,
        text="Sil",
        command=gui.delete_sl_level
    )
    gui.delete_sl_btn.pack(side=tk.LEFT, padx=5, pady=5)

    # Trailing stop loss
    trailing_frame = ttk.Frame(frame)
    trailing_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Label(
        trailing_frame,
        text="Trailing Stop-Loss (%):"
    ).pack(side=tk.LEFT, padx=5, pady=5)

    # Trailing stop loss için de master parametresini ekle
    gui.trailing_sl_var = tk.StringVar(master=frame, value=str(trade_settings.get("trailing_stop_loss", 5.0)))

    gui.trailing_sl_entry = ttk.Entry(
        trailing_frame,
        width=10,
        textvariable=gui.trailing_sl_var
    )
    gui.trailing_sl_entry.pack(side=tk.LEFT, padx=5, pady=5)


def create_trade_behavior_settings(gui, frame):
    """İşlem davranışı ayarları sekmesini oluşturur"""
    # Sol taraf - Alım/Satım Davranışları
    left_frame = ttk.Frame(frame)
    left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Alım davranışları
    buy_frame = ttk.LabelFrame(left_frame, text="Alım Davranışları")
    buy_frame.pack(fill=tk.X, padx=5, pady=5)

    # Momentum alımı
    momentum_frame = ttk.Frame(buy_frame)
    momentum_frame.pack(fill=tk.X, padx=5, pady=2)

    # BooleanVar değişkenlerini oluştur (varsayılan değerlerle)
    momentum_enabled = trade_settings.get("momentum_enabled", False)
    gui.momentum_var = tk.BooleanVar(master=frame, value=momentum_enabled)

    ttk.Checkbutton(
        momentum_frame,
        text="Momentum Tabanlı Alım",
        variable=gui.momentum_var
    ).pack(side=tk.LEFT, padx=5)

    ttk.Label(
        momentum_frame,
        text="Eşik (%):"
    ).pack(side=tk.LEFT, padx=5)

    gui.momentum_threshold_var = tk.StringVar(master=frame, value=str(trade_settings.get("momentum_threshold", 5.0)))
    ttk.Entry(
        momentum_frame,
        width=5,
        textvariable=gui.momentum_threshold_var
    ).pack(side=tk.LEFT, padx=0)

    # Dip alımı
    dip_frame = ttk.Frame(buy_frame)
    dip_frame.pack(fill=tk.X, padx=5, pady=2)

    dip_buy_enabled = trade_settings.get("dip_buy_enabled", False)
    gui.dip_buy_var = tk.BooleanVar(master=frame, value=dip_buy_enabled)

    ttk.Checkbutton(
        dip_frame,
        text="Dip Alımı",
        variable=gui.dip_buy_var
    ).pack(side=tk.LEFT, padx=5)

    ttk.Label(
        dip_frame,
        text="Eşik (%):"
    ).pack(side=tk.LEFT, padx=5)

    gui.dip_threshold_var = tk.StringVar(master=frame, value=str(trade_settings.get("dip_buy_threshold", 15.0)))
    ttk.Entry(
        dip_frame,
        width=5,
        textvariable=gui.dip_threshold_var
    ).pack(side=tk.LEFT, padx=0)

    # Mikro pump alımı
    micro_frame = ttk.Frame(buy_frame)
    micro_frame.pack(fill=tk.X, padx=5, pady=2)

    micro_pump_enabled = trade_settings.get("micro_pump_detection_enabled", False)
    gui.micro_pump_var = tk.BooleanVar(master=frame, value=micro_pump_enabled)

    ttk.Checkbutton(
        micro_frame,
        text="Mikro Pump Alımı",
        variable=gui.micro_pump_var
    ).pack(side=tk.LEFT, padx=5)

    ttk.Label(
        micro_frame,
        text="Eşik (%):"
    ).pack(side=tk.LEFT, padx=5)

    gui.micro_threshold_var = tk.StringVar(master=frame, value=str(trade_settings.get("micro_pump_threshold", 3.0)))
    ttk.Entry(
        micro_frame,
        width=5,
        textvariable=gui.micro_threshold_var
    ).pack(side=tk.LEFT, padx=0)

    # Satım davranışları
    sell_frame = ttk.LabelFrame(left_frame, text="Satım Davranışları")
    sell_frame.pack(fill=tk.X, padx=5, pady=5)

    # Likidite çıkışı
    liquidity_frame = ttk.Frame(sell_frame)
    liquidity_frame.pack(fill=tk.X, padx=5, pady=2)

    liquidity_exit_enabled = trade_settings.get("liquidity_exit_enabled", False)
    gui.liquidity_exit_var = tk.BooleanVar(master=frame, value=liquidity_exit_enabled)

    ttk.Checkbutton(
        liquidity_frame,
        text="Likidite Çıkış Stratejisi",
        variable=gui.liquidity_exit_var
    ).pack(side=tk.LEFT, padx=5)

    ttk.Label(
        liquidity_frame,
        text="Eşik (%):"
    ).pack(side=tk.LEFT, padx=5)

    gui.liquidity_threshold_var = tk.StringVar(master=frame, value=str(trade_settings.get("liquidity_exit_threshold", 25.0)))
    ttk.Entry(
        liquidity_frame,
        width=5,
        textvariable=gui.liquidity_threshold_var
    ).pack(side=tk.LEFT, padx=0)

    # Balina dump tespiti
    whale_frame = ttk.Frame(sell_frame)
    whale_frame.pack(fill=tk.X, padx=5, pady=2)

    whale_dump_enabled = trade_settings.get("whale_dump_detection_enabled", False)
    gui.whale_dump_var = tk.BooleanVar(master=frame, value=whale_dump_enabled)

    ttk.Checkbutton(
        whale_frame,
        text="Balina Dump Tespiti",
        variable=gui.whale_dump_var
    ).pack(side=tk.LEFT, padx=5)

    ttk.Label(
        whale_frame,
        text="Eşik (SOL):"
    ).pack(side=tk.LEFT, padx=5)

    gui.whale_threshold_var = tk.StringVar(master=frame, value=str(trade_settings.get("whale_dump_threshold", 10.0)))
    ttk.Entry(
        whale_frame,
        width=5,
        textvariable=gui.whale_threshold_var
    ).pack(side=tk.LEFT, padx=0)

    # Hacim düşüşü
    volume_frame = ttk.Frame(sell_frame)
    volume_frame.pack(fill=tk.X, padx=5, pady=2)

    volume_drop_enabled = trade_settings.get("volume_drop_detection_enabled", False)
    gui.volume_drop_var = tk.BooleanVar(master=frame, value=volume_drop_enabled)

    ttk.Checkbutton(
        volume_frame,
        text="Hacim Düşüşü Tespiti",
        variable=gui.volume_drop_var
    ).pack(side=tk.LEFT, padx=5)

    ttk.Label(
        volume_frame,
        text="Eşik (%):"
    ).pack(side=tk.LEFT, padx=5)

    gui.volume_threshold_var = tk.StringVar(master=frame, value=str(trade_settings.get("volume_drop_threshold", 40.0)))
    ttk.Entry(
        volume_frame,
        width=5,
        textvariable=gui.volume_threshold_var
    ).pack(side=tk.LEFT, padx=0)

    # Sağ taraf - Diğer Davranışlar
    right_frame = ttk.Frame(frame)
    right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Token çeşitlendirme
    diversification_frame = ttk.LabelFrame(right_frame, text="Token Çeşitlendirme")
    diversification_frame.pack(fill=tk.X, padx=5, pady=5)

    diversification_enabled = trade_settings.get("token_diversification_enabled", False)
    gui.diversification_var = tk.BooleanVar(master=frame, value=diversification_enabled)

    ttk.Checkbutton(
        diversification_frame,
        text="Token Çeşitlendirme",
        variable=gui.diversification_var
    ).pack(anchor=tk.W, padx=5, pady=2)

    token_cat_frame = ttk.Frame(diversification_frame)
    token_cat_frame.pack(fill=tk.X, padx=5, pady=2)

    ttk.Label(
        token_cat_frame,
        text="Maksimum Token Kategorisi:"
    ).pack(side=tk.LEFT, padx=5)

    gui.max_category_var = tk.StringVar(master=frame, value=str(trade_settings.get("max_token_category", 3)))
    ttk.Entry(
        token_cat_frame,
        width=5,
        textvariable=gui.max_category_var
    ).pack(side=tk.LEFT, padx=0)

    pos_cat_frame = ttk.Frame(diversification_frame)
    pos_cat_frame.pack(fill=tk.X, padx=5, pady=2)

    ttk.Label(
        pos_cat_frame,
        text="Kategori Başına Pozisyon:"
    ).pack(side=tk.LEFT, padx=5)

    gui.pos_per_cat_var = tk.StringVar(master=frame, value=str(trade_settings.get("max_positions_per_category", 2)))
    ttk.Entry(
        pos_cat_frame,
        width=5,
        textvariable=gui.pos_per_cat_var
    ).pack(side=tk.LEFT, padx=0)

    # Gece modu
    night_frame = ttk.LabelFrame(right_frame, text="Gece Modu")
    night_frame.pack(fill=tk.X, padx=5, pady=5)

    night_mode_enabled = trade_settings.get("night_mode_enabled", False)
    gui.night_mode_var = tk.BooleanVar(master=frame, value=night_mode_enabled)

    ttk.Checkbutton(
        night_frame,
        text="Gece Modu",
        variable=gui.night_mode_var
    ).pack(anchor=tk.W, padx=5, pady=2)

    time_frame = ttk.Frame(night_frame)
    time_frame.pack(fill=tk.X, padx=5, pady=2)

    ttk.Label(
        time_frame,
        text="Başlangıç:"
    ).grid(
        row=0,
        column=0,
        sticky=tk.W,
        padx=5,
        pady=2
    )

    gui.night_start_var = tk.StringVar(master=frame, value=trade_settings.get("night_mode_start", "00:00"))
    ttk.Entry(
        time_frame,
        width=8,
        textvariable=gui.night_start_var
    ).grid(
        row=0,
        column=1,
        sticky=tk.W,
        padx=5,
        pady=2
    )

    ttk.Label(
        time_frame,
        text="Bitiş:"
    ).grid(
        row=1,
        column=0,
        sticky=tk.W,
        padx=5,
        pady=2
    )

    gui.night_end_var = tk.StringVar(master=frame, value=trade_settings.get("night_mode_end", "08:00"))
    ttk.Entry(
        time_frame,
        width=8,
        textvariable=gui.night_end_var
    ).grid(
        row=1,
        column=1,
        sticky=tk.W,
        padx=5,
        pady=2
    )

    ttk.Label(
        time_frame,
        text="Bakiye Limiti (%):"
    ).grid(
        row=2,
        column=0,
        sticky=tk.W,
        padx=5,
        pady=2
    )

    gui.night_limit_var = tk.StringVar(master=frame, value=str(trade_settings.get("night_mode_limit", 30)))
    ttk.Entry(
        time_frame,
        width=8,
        textvariable=gui.night_limit_var
    ).grid(
        row=2,
        column=1,
        sticky=tk.W,
        padx=5,
        pady=2
    )

    # Snipe modu
    snipe_frame = ttk.LabelFrame(right_frame, text="Snipe Modu")
    snipe_frame.pack(fill=tk.X, padx=5, pady=5)

    sniping_enabled = trade_settings.get("sniping_enabled", False)
    gui.sniping_var = tk.BooleanVar(master=frame, value=sniping_enabled)

    ttk.Checkbutton(
        snipe_frame,
        text="Sniping Özelliği",
        variable=gui.sniping_var
    ).pack(anchor=tk.W, padx=5, pady=2)

    snipe_pct_frame = ttk.Frame(snipe_frame)
    snipe_pct_frame.pack(fill=tk.X, padx=5, pady=2)

    ttk.Label(
        snipe_pct_frame,
        text="Maksimum Yüzde (%):"
    ).pack(side=tk.LEFT, padx=5)

    gui.snipe_pct_var = tk.StringVar(master=frame, value=str(trade_settings.get("sniping_max_percentage", 20)))
    ttk.Entry(
        snipe_pct_frame,
        width=5,
        textvariable=gui.snipe_pct_var
    ).pack(side=tk.LEFT, padx=0)


def create_advanced_settings(gui, frame):
    """Gelişmiş ayarlar sekmesini oluşturur"""
    # Sol taraf - Performans ve optimizasyon
    left_frame = ttk.Frame(frame)
    left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Döngü ayarları
    cycle_frame = ttk.LabelFrame(left_frame, text="İşlem Döngüsü")
    cycle_frame.pack(fill=tk.X, padx=5, pady=5)

    rapid_cycle_enabled = trade_settings.get("rapid_cycle_enabled", False)
    gui.rapid_cycle_var = tk.BooleanVar(master=frame, value=rapid_cycle_enabled)

    ttk.Checkbutton(
        cycle_frame,
        text="Hızlı Döngü",
        variable=gui.rapid_cycle_var
    ).pack(anchor=tk.W, padx=5, pady=2)

    interval_frame = ttk.Frame(cycle_frame)
    interval_frame.pack(fill=tk.X, padx=5, pady=2)

    ttk.Label(
        interval_frame,
        text="Döngü Aralığı (saniye):"
    ).pack(side=tk.LEFT, padx=5)

    gui.cycle_interval_var = tk.StringVar(master=frame, value=str(trade_settings.get("rapid_cycle_interval", 0.5)))
    ttk.Entry(
        interval_frame,
        width=5,
        textvariable=gui.cycle_interval_var
    ).pack(side=tk.LEFT, padx=0)

    # Slipaj optimizasyonu
    slippage_frame = ttk.LabelFrame(left_frame, text="Slipaj Ayarları")
    slippage_frame.pack(fill=tk.X, padx=5, pady=5)

    auto_slippage_adjust = trade_settings.get("auto_slippage_adjust", False)
    gui.auto_slippage_var = tk.BooleanVar(master=frame, value=auto_slippage_adjust)

    ttk.Checkbutton(
        slippage_frame,
        text="Otomatik Slipaj Ayarı",
        variable=gui.auto_slippage_var
    ).pack(anchor=tk.W, padx=5, pady=2)

    base_slippage_frame = ttk.Frame(slippage_frame)
    base_slippage_frame.pack(fill=tk.X, padx=5, pady=2)

    ttk.Label(
        base_slippage_frame,
        text="Temel Slipaj (%):"
    ).pack(side=tk.LEFT, padx=5)

    gui.slippage_var = tk.StringVar(master=frame, value=str(trade_settings.get("slippage_tolerance", 1)))
    ttk.Entry(
        base_slippage_frame,
        width=5,
        textvariable=gui.slippage_var
    ).pack(side=tk.LEFT, padx=0)

    # Gas fee optimizasyonu
    gas_frame = ttk.LabelFrame(left_frame, text="Gas Ücreti Optimizasyonu")
    gas_frame.pack(fill=tk.X, padx=5, pady=5)

    gas_fee_optimization = trade_settings.get("gas_fee_optimization", False)
    gui.gas_optimization_var = tk.BooleanVar(master=frame, value=gas_fee_optimization)

    ttk.Checkbutton(
        gas_frame,
        text="Gas Ücreti Optimizasyonu",
        variable=gui.gas_optimization_var
    ).pack(anchor=tk.W, padx=5, pady=2)

    # Sağ taraf - Fiyat ve volatilite
    right_frame = ttk.Frame(frame)
    right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Volatilite işlemleri
    volatility_frame = ttk.LabelFrame(right_frame, text="Volatilite Tabanlı İşlemler")
    volatility_frame.pack(fill=tk.X, padx=5, pady=5)

    volatility_trading_enabled = trade_settings.get("volatility_trading_enabled", False)
    gui.volatility_var = tk.BooleanVar(master=frame, value=volatility_trading_enabled)

    ttk.Checkbutton(
        volatility_frame,
        text="Volatilite Tabanlı İşlem",
        variable=gui.volatility_var
    ).pack(anchor=tk.W, padx=5, pady=2)

    vol_threshold_frame = ttk.Frame(volatility_frame)
    vol_threshold_frame.pack(fill=tk.X, padx=5, pady=2)

    ttk.Label(
        vol_threshold_frame,
        text="Volatilite Eşiği (%):"
    ).pack(side=tk.LEFT, padx=5)

    gui.volatility_threshold_var = tk.StringVar(master=frame, value=str(trade_settings.get("volatility_threshold", 8.0)))
    ttk.Entry(
        vol_threshold_frame,
        width=5,
        textvariable=gui.volatility_threshold_var
    ).pack(side=tk.LEFT, padx=0)

    # Fiyat sapması
    deviation_frame = ttk.LabelFrame(right_frame, text="Fiyat Sapması Tespiti")
    deviation_frame.pack(fill=tk.X, padx=5, pady=5)

    price_deviation_enabled = trade_settings.get("price_deviation_enabled", False)
    gui.price_deviation_var = tk.BooleanVar(master=frame, value=price_deviation_enabled)

    ttk.Checkbutton(
        deviation_frame,
        text="Fiyat Sapması Tespiti",
        variable=gui.price_deviation_var
    ).pack(anchor=tk.W, padx=5, pady=2)

    dev_threshold_frame = ttk.Frame(deviation_frame)
    dev_threshold_frame.pack(fill=tk.X, padx=5, pady=2)

    ttk.Label(
        dev_threshold_frame,
        text="Sapma Eşiği (Z-skor):"
    ).pack(side=tk.LEFT, padx=5)

    gui.deviation_threshold_var = tk.StringVar(master=frame, value=str(trade_settings.get("price_deviation_threshold", 3.0)))
    ttk.Entry(
        dev_threshold_frame,
        width=5,
        textvariable=gui.deviation_threshold_var
    ).pack(side=tk.LEFT, padx=0)

    # Pump algılama
    pump_frame = ttk.LabelFrame(right_frame, text="Pump Algılama")
    pump_frame.pack(fill=tk.X, padx=5, pady=5)

    # Pump algılama penceresi
    pump_window_frame = ttk.Frame(pump_frame)
    pump_window_frame.pack(fill=tk.X, padx=5, pady=2)

    ttk.Label(
        pump_window_frame,
        text="Algılama Penceresi (saniye):"
    ).pack(side=tk.LEFT, padx=5)

    gui.pump_window_var = tk.StringVar(master=frame, value=str(trade_settings.get("momentum_window", 5)))
    ttk.Entry(
        pump_window_frame,
        width=5,
        textvariable=gui.pump_window_var
    ).pack(side=tk.LEFT, padx=0)

    # Dump algılama
    dump_frame = ttk.Frame(pump_frame)
    dump_frame.pack(fill=tk.X, padx=5, pady=2)

    ttk.Label(
        dump_frame,
        text="Dump Algılama Yüzdesi (%):"
    ).pack(side=tk.LEFT, padx=5)

    gui.dump_pct_var = tk.StringVar(master=frame, value=str(trade_settings.get("dump_detection_percentage", 60)))
    ttk.Entry(
        dump_frame,
        width=5,
        textvariable=gui.dump_pct_var
    ).pack(side=tk.LEFT, padx=0)

    ttk.Label(
        dump_frame,
        text="Pencere (saniye):"
    ).pack(side=tk.LEFT, padx=5)

    gui.dump_window_var = tk.StringVar(master=frame, value=str(trade_settings.get("dump_time_window", 5)))
    ttk.Entry(
        dump_frame,
        width=5,
        textvariable=gui.dump_window_var
    ).pack(side=tk.LEFT, padx=0)
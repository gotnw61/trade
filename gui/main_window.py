# -*- coding: utf-8 -*-
"""
Ana GUI penceresi - TradeBotGUI sınıfı ve yardımcı fonksiyonlar
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import matplotlib.pyplot as plt
import asyncio
import threading
import time
from datetime import datetime
import nest_asyncio

# Event loop'ları düzeltir - asyncio çakışmalarını önler
try:
    nest_asyncio.apply()
except Exception:
    pass  # nest_asyncio yoksa devam et

# GUI modülleri
from gotnw_tradebot.config import trade_settings, current_strategy
from gotnw_tradebot.utils.logging_utils import log_to_file


def run_async(coroutine, callback=None, root=None):
    """
    Asenkron bir coroutine'i çalıştırır
    
    Args:
        coroutine: Çalıştırılacak coroutine
        callback: Sonuç için geri çağırma fonksiyonu
        root: Tkinter root nesnesi (isteğe bağlı, callback için gerekli)
        
    Returns:
        asyncio.Future: Future nesnesi
    """
    def _callback_wrapper(future):
        """Future'ın sonucunu alıp callback'e gönderir"""
        try:
            result = future.result()
            if callback and root and root.winfo_exists():
                root.after(0, lambda: callback(result))
        except Exception as e:
            print(f"Async çalıştırma hatası (callback): {e}")
            if callback and root and root.winfo_exists():
                root.after(0, lambda: callback(None))
    
    try:
        # Mevcut event loop'u kullan
        loop = asyncio.get_event_loop()
        
        # Burada Future oluşturuyoruz, task değil
        future = asyncio.ensure_future(coroutine)
        
        # Callback ekle
        if callback:
            future.add_done_callback(_callback_wrapper)
            
        return future
    except Exception as e:
        print(f"Async çalıştırma hatası (genel): {e}")
        import traceback
        traceback.print_exc()
        return None


class TradeBotGUI:
    """
    TradeBot için ana GUI sınıfı
    """
    def __init__(self, root, trade_bot):
        """
        GUI sınıfını başlatır
        
        Args:
            root (tk.Tk): Tkinter ana penceresi
            trade_bot: TradeBot örneği
        """
        self.root = root
        self.trade_bot = trade_bot
        self.wallet_manager = trade_bot.wallet
        self.active_tasks = []
        self.create_variables(root)
        self.create_gui()
        self.timer = None
        self.update_info()

    def create_variables(self, root):
        """
        Tüm Tkinter değişkenlerini oluşturur
        
        Args:
            root: Tkinter ana penceresi
        """
        # Temel ayarlar değişkenleri
        autobuy_value = trade_settings.get("autobuy_enabled", False)
        autosell_value = trade_settings.get("autosell_enabled", False)
        simulation_value = trade_settings.get("simulation_mode", False)

        self.autobuy_var = tk.BooleanVar(master=root, value=autobuy_value)
        self.autosell_var = tk.BooleanVar(master=root, value=autosell_value)
        self.simulation_var = tk.BooleanVar(master=root, value=simulation_value)

        # Ticaret parametreleri değişkenleri
        self.buy_amount_var = tk.StringVar(master=root, value=str(trade_settings.get("buy_amount_sol", 0.2)))
        self.min_liquidity_var = tk.StringVar(master=root, value=str(trade_settings.get("min_liquidity_usd", 5000)))
        self.max_positions_var = tk.StringVar(master=root, value=str(trade_settings.get("max_positions", 5)))
        self.min_balance_var = tk.StringVar(master=root, value=str(trade_settings.get("min_balance_sol", 0.005)))
        self.max_loss_var = tk.StringVar(master=root, value=str(trade_settings.get("max_portfolio_loss", 30)))
        self.strategy_var = tk.StringVar(master=root, value=current_strategy)

        # AI değişkenleri
        self.pump_detection_var = tk.BooleanVar(master=root, value=trade_settings.get("ai_enabled", False))
        self.duration_prediction_var = tk.BooleanVar(master=root, value=trade_settings.get("ai_pump_duration_prediction_enabled", False))
        self.confidence_var = tk.StringVar(master=root, value=str(trade_settings.get("ai_confidence_threshold", 0.7)))

        # Diğer Boolean değişkenleri
        bool_var_mappings = [
            ('momentum_var', 'momentum_enabled', True),
            ('dip_buy_var', 'dip_buy_enabled', True),
            ('micro_pump_var', 'micro_pump_detection_enabled', True),
            ('liquidity_exit_var', 'liquidity_exit_enabled', True),
            ('whale_dump_var', 'whale_dump_detection_enabled', True),
            ('volume_drop_var', 'volume_drop_detection_enabled', True),
            ('diversification_var', 'token_diversification_enabled', True),
            ('night_mode_var', 'night_mode_enabled', False),
            ('sniping_var', 'sniping_enabled', False),
            ('rapid_cycle_var', 'rapid_cycle_enabled', True),
            ('auto_slippage_var', 'auto_slippage_adjust', True),
            ('gas_optimization_var', 'gas_fee_optimization', True),
            ('volatility_var', 'volatility_trading_enabled', True),
            ('price_deviation_var', 'price_deviation_enabled', True)
        ]

        for var_name, setting_name, default_value in bool_var_mappings:
            var = tk.BooleanVar(master=root, value=trade_settings.get(setting_name, default_value))
            setattr(self, var_name, var)

    def create_gui(self):
        """Ana GUI bileşenlerini oluşturur"""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Frame'leri oluştur
        self.dashboard_frame = ttk.Frame(self.notebook)
        self.trades_frame = ttk.Frame(self.notebook)
        self.wallet_frame = ttk.Frame(self.notebook)
        self.settings_frame = ttk.Frame(self.notebook)
        self.ai_frame = ttk.Frame(self.notebook)

        # Notebook'a sekmeleri ekle
        self.notebook.add(self.dashboard_frame, text="Kontrol Paneli")
        self.notebook.add(self.trades_frame, text="İşlemler")
        self.notebook.add(self.wallet_frame, text="Cüzdan")
        self.notebook.add(self.settings_frame, text="Ayarlar")
        self.notebook.add(self.ai_frame, text="Yapay Zeka")

        # Her sekmenin içerik modüllerini import et
        from gotnw_tradebot.gui.dashboard import create_dashboard
        from gotnw_tradebot.gui.trades_panel import create_trades_panel
        from gotnw_tradebot.gui.wallet_panel import create_wallet_panel
        from gotnw_tradebot.gui.settings_panel import create_settings_panel
        from gotnw_tradebot.gui.ai_panel import create_ai_panel

        # Her sekmenin içeriğini oluştur
        create_dashboard(self)
        create_trades_panel(self)
        create_wallet_panel(self)
        create_settings_panel(self)
        create_ai_panel(self)

    def on_closing(self):
        """Uygulama kapatılırken yapılacak işlemler"""
        if messagebox.askokcancel("Çıkış", "Programdan çıkmak istiyor musunuz?"):
            print("Uygulama kapatılıyor...")
            
            # Timer'ı iptal et
            if self.timer:
                try:
                    self.root.after_cancel(self.timer)
                    print("Timer iptal edildi")
                except Exception:
                    pass

            # Aktif görevleri iptal et
            for task in self.active_tasks:
                if not task.done():
                    try:
                        task.cancel()
                        print("Aktif görev iptal edildi")
                    except Exception:
                        pass

            # WebSocket'i durdur
            if hasattr(self.trade_bot, 'websocket_active') and self.trade_bot.websocket_active:
                try:
                    print("WebSocket kapatılıyor")
                    self.trade_bot.websocket_active = False
                except Exception:
                    pass

            # Konsolu temizle
            try:
                import sys
                sys.stdout.flush()
            except Exception:
                pass
                
            # Direk olarak kapat
            print("GUI kapatılıyor...")
            self.root.destroy()
            print("GUI başarıyla kapatıldı.")

    def update_info(self):
        """Durum bilgilerini periyodik olarak günceller"""
        try:
            print("Durum bilgileri güncelleniyor...")
            # Wallet bilgisini göster
            if (hasattr(self.wallet_manager, 'active_wallet_index') and
                hasattr(self.wallet_manager, 'wallets') and
                self.wallet_manager.active_wallet_index >= 0 and 
                len(self.wallet_manager.wallets) > self.wallet_manager.active_wallet_index):
                
                wallet = self.wallet_manager.wallets[self.wallet_manager.active_wallet_index]
                if "keypair" in wallet:
                    wallet_address = str(wallet["keypair"].pubkey())
                    self.wallet_address_label.config(text=wallet_address[:10] + "..." + wallet_address[-5:])
                    print(f"Cüzdan adresi güncellendi: {wallet_address[:10]}...{wallet_address[-5:]}")
            else:
                self.wallet_address_label.config(text="Bağlı değil")
                print("Bağlı cüzdan bulunamadı.")

            # Bakiye bilgisini güncelle (senkron olarak)
            def update_balance_display(balance):
                if balance is not None and isinstance(balance, (int, float)):
                    # Bakiyeyi göster
                    self.balance_label.config(text=f"{balance:.4f}")
                    print(f"Bakiye güncellendi: {balance:.4f}")
                    
                    # SOL fiyatını getir ve göster
                    from gotnw_tradebot.utils.network_utils import get_sol_price
                    
                    async def fetch_sol_price():
                        sol_price = await get_sol_price()
                        return sol_price
                    
                    def update_price_display(sol_price):
                        if sol_price is not None and isinstance(sol_price, (int, float)):
                            self.sol_price_label.config(text=f"${sol_price:.2f}")
                            usd_balance = balance * sol_price
                            self.usd_balance_label.config(text=f"${usd_balance:.2f}")
                            print(f"SOL fiyatı güncellendi: ${sol_price:.2f}, USD değeri: ${usd_balance:.2f}")
                    
                    # Sol fiyatını al
                    future = run_async(fetch_sol_price(), update_price_display, self.root)
                    if future:
                        self.active_tasks.append(future)
                else:
                    print(f"Geçersiz bakiye: {balance}")
                    self.balance_label.config(text="0.00")
                    self.usd_balance_label.config(text="$0.00")

            # Bakiyeyi al
            if hasattr(self.wallet_manager, 'get_balance'):
                async def fetch_balance():
                    try:
                        return await self.wallet_manager.get_balance()
                    except Exception as e:
                        print(f"Bakiye alma hatası: {e}")
                        return 0.0
                        
                # Bakiyeyi asenkron olarak al
                future = run_async(fetch_balance(), update_balance_display, self.root)
                if future:
                    self.active_tasks.append(future)
            
            # Bot durumunu göster
            try:
                bot_active = getattr(self.trade_bot, 'websocket_active', False)
                self.bot_status_label.config(
                    text="Çalışıyor" if bot_active else "Durduruldu",
                    foreground="green" if bot_active else "red"
                )
                print(f"Bot durumu güncellendi: {'Çalışıyor' if bot_active else 'Durduruldu'}")
            except Exception as e:
                print(f"Bot durumu kontrol hatası: {e}")
                self.bot_status_label.config(text="Bilinmeyen", foreground="orange")

            # Strateji ve mod bilgisini göster
            self.strategy_label.config(text=current_strategy.capitalize())
            self.mode_label.config(text="Simülasyon" if trade_settings["simulation_mode"] else "Gerçek")
            self.autobuy_var.set(trade_settings["autobuy_enabled"])
            self.autosell_var.set(trade_settings["autosell_enabled"])
            print(f"Strateji ve mod bilgisi güncellendi: {current_strategy}, Simülasyon: {trade_settings['simulation_mode']}")

            # Pozisyonları yenile
            self.refresh_positions()
            print("Pozisyonlar yenilendi.")

            # Tamamlanan görevleri temizle
            self.active_tasks = [task for task in self.active_tasks if not task.done()]

            # Timer'ı yeniden ayarla
            self.timer = self.root.after(5000, self.update_info)
            print("Durum güncelleme tamamlandı. Bir sonraki güncelleme 5 saniye sonra.")

        except Exception as e:
            print(f"Durum güncelleme hatası: {e}")
            import traceback
            traceback.print_exc()
            self.timer = self.root.after(5000, self.update_info)

    def log_message(self, message):
        """
        Log mesajını ekler
        
        Args:
            message (str): Log mesajı
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        if hasattr(self, 'log_text'):
            self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
            self.log_text.see(tk.END)

        log_to_file(message)

    def stop_bot(self):
        """Botu durdurma işlevi"""
        if not getattr(self.trade_bot, 'websocket_active', False):
            return

        async def stop_websocket():
            await self.trade_bot.stop_websocket()
            self.log_message("Bot durduruldu.")

        task = run_async(stop_websocket(), root=self.root)
        if task:
            self.active_tasks.append(task)
        self.stop_bot_btn.config(state=tk.DISABLED)
        self.start_bot_btn.config(state=tk.NORMAL)

    def start_bot(self):
        """Botu başlatma işlevi"""
        if getattr(self.trade_bot, 'websocket_active', False):
            return

        async def start_bot_async():
            try:
                await self.trade_bot.start_enhanced_websocket()
                await self.trade_bot.monitor_positions()
                self.log_message("Bot başlatıldı.")
            except Exception as e:
                self.log_message(f"Bot başlatma hatası: {e}")
        
        task = run_async(start_bot_async(), root=self.root)
        if task:
            self.active_tasks.append(task)
        
        self.start_bot_btn.config(state=tk.DISABLED)
        self.stop_bot_btn.config(state=tk.NORMAL)

    def toggle_autobuy(self):
        """Otomatik alım özelliğini açıp kapatır"""
        trade_settings["autobuy_enabled"] = self.autobuy_var.get()
        status = "açıldı" if self.autobuy_var.get() else "kapatıldı"
        self.log_message(f"Otomatik alım özelliği {status}")

    def toggle_autosell(self):
        """Otomatik satım özelliğini açıp kapatır"""
        trade_settings["autosell_enabled"] = self.autosell_var.get()
        status = "açıldı" if self.autosell_var.get() else "kapatıldı"
        self.log_message(f"Otomatik satım özelliği {status}")

    def toggle_simulation(self):
        """Simülasyon modunu açıp kapatır"""
        trade_settings["simulation_mode"] = self.simulation_var.get()
        status = "açıldı" if self.simulation_var.get() else "kapatıldı"
        self.log_message(f"Simülasyon modu {status}")
        self.mode_label.config(text="Simülasyon" if trade_settings["simulation_mode"] else "Gerçek")

    def toggle_pump_detection(self):
        """Toggles pump detection AI feature"""
        trade_settings["ai_enabled"] = self.pump_detection_var.get()
        status = "açıldı" if self.pump_detection_var.get() else "kapatıldı"
        self.log_message(f"Pump Algılama özelliği {status}")

    def toggle_pump_duration_prediction(self):
        """Toggles pump duration prediction AI feature"""
        trade_settings["ai_pump_duration_prediction_enabled"] = self.duration_prediction_var.get()
        status = "açıldı" if self.duration_prediction_var.get() else "kapatıldı"
        self.log_message(f"Pump Süresi Tahmini özelliği {status}")

    def set_ai_confidence_threshold(self):
        """Sets the AI confidence threshold"""
        try:
            threshold = float(self.confidence_var.get())
            if 0 < threshold <= 1:
                trade_settings["ai_confidence_threshold"] = threshold
                self.log_message(f"AI güven eşiği {threshold} olarak ayarlandı")
                messagebox.showinfo("Ayar Başarılı", f"AI güven eşiği {threshold} olarak güncellendi")
            else:
                raise ValueError("Eşik 0 ile 1 arasında olmalıdır")
        except ValueError as e:
            self.log_message(f"Geçersiz güven eşiği: {e}")
            messagebox.showerror("Ayar Hatası", "Lütfen 0 ile 1 arasında geçerli bir değer girin")

    def train_ai_models(self):
        """Trains AI models for the trading bot"""
        try:
            self.ai_ax.clear()
            pump_success = self.trade_bot.analyzer.train_pump_detection_model()
            duration_success = self.trade_bot.analyzer.train_pump_duration_model()
            price_success = self.trade_bot.analyzer.train_price_prediction_model()

            if pump_success or duration_success or price_success:
                self.log_message("✅ AI modelleri başarıyla eğitildi!")
                self.show_ai_performance()
            else:
                self.log_message("❌ AI modelleri eğitilemedi, yeterli veri bulunamadı.")
                messagebox.showwarning("Eğitim Hatası", "AI modelleri eğitilemedi. Yeterli veri bulunmuyor.")

        except Exception as e:
            error_msg = f"AI model eğitimi hatası: {e}"
            self.log_message(error_msg)
            messagebox.showerror("Eğitim Hatası", error_msg)

    def load_ai_models(self):
        """Loads pre-trained AI models"""
        try:
            filepath = filedialog.askopenfilename(
                title="AI Modellerini Seç",
                filetypes=[("Pickle Files", "*.pkl")]
            )

            if filepath:
                model_prefix = os.path.splitext(os.path.basename(filepath))[0]
                self.trade_bot.analyzer.load_models(model_prefix)
                self.log_message(f"✅ AI modelleri yüklendi: {model_prefix}")
                messagebox.showinfo("Model Yükleme", f"Modeller başarıyla yüklendi: {model_prefix}")
                self.show_ai_performance()

        except Exception as e:
            error_msg = f"Model yükleme hatası: {e}"
            self.log_message(error_msg)
            messagebox.showerror("Yükleme Hatası", error_msg)

    def save_ai_models(self):
        """Saves current AI models"""
        try:
            filepath = filedialog.asksaveasfilename(
                defaultextension=".pkl",
                filetypes=[("Pickle Files", "*.pkl")]
            )

            if filepath:
                model_prefix = os.path.splitext(os.path.basename(filepath))[0]
                self.trade_bot.analyzer.save_models(model_prefix)
                self.log_message(f"✅ AI modelleri kaydedildi: {model_prefix}")
                messagebox.showinfo("Model Kaydetme", f"Modeller başarıyla kaydedildi: {model_prefix}")

        except Exception as e:
            error_msg = f"Model kaydetme hatası: {e}"
            self.log_message(error_msg)
            messagebox.showerror("Kaydetme Hatası", error_msg)

    def show_ai_performance(self):
        """Displays AI model performance metrics"""
        try:
            self.ai_ax.clear()
            metrics = self.trade_bot.analyzer.model_metrics

            models = list(metrics.keys())
            precision_scores = [metrics[model].get('precision', 0) for model in models]
            recall_scores = [metrics[model].get('recall', 0) for model in models]
            f1_scores = [metrics[model].get('f1', 0) for model in models]
            r2_scores = [metrics[model].get('r2', 0) for model in models]

            bar_width = 0.2
            index = range(len(models))

            self.ai_ax.bar([i - bar_width*1.5 for i in index], precision_scores, bar_width, label='Precision', color='blue')
            self.ai_ax.bar([i - bar_width/2 for i in index], recall_scores, bar_width, label='Recall', color='green')
            self.ai_ax.bar([i + bar_width/2 for i in index], f1_scores, bar_width, label='F1 Score', color='red')
            self.ai_ax.bar([i + bar_width*1.5 for i in index], r2_scores, bar_width, label='R² Score', color='purple')

            self.ai_ax.set_xlabel('Modeller')
            self.ai_ax.set_ylabel('Performans Skoru')
            self.ai_ax.set_title('AI Model Performans Metrikleri')
            self.ai_ax.set_xticks(index)
            self.ai_ax.set_xticklabels(models, rotation=45)
            self.ai_ax.legend()
            self.ai_canvas.draw()

            performance_msg = "Model Performans Detayları:\n"
            for model, scores in metrics.items():
                performance_msg += f"{model.capitalize()} Model:\n"
                for metric, value in scores.items():
                    performance_msg += f"  {metric.capitalize()}: {value:.4f}\n"
            self.log_message(performance_msg)

        except Exception as e:
            error_msg = f"Performans görselleştirme hatası: {e}"
            self.log_message(error_msg)
            messagebox.showerror("Görselleştirme Hatası", error_msg)

    def refresh_positions(self):
        """Mevcut pozisyonları günceller"""
        try:
            for i in self.positions_table.get_children():
                self.positions_table.delete(i)

            for mint_address, position in self.trade_bot.positions.items():
                try:
                    current_price = self.trade_bot.websocket_prices.get(mint_address, position['buy_price'])
                    profit_loss_pct = ((current_price - position['buy_price']) / position['buy_price']) * 100

                    async def get_token_info_async():
                        return await self.trade_bot.get_token_info(mint_address)
                    
                    token_info = None
                    try:
                        task = run_async(get_token_info_async(), root=self.root)
                        token_info = task.result() if task.done() else None
                    except Exception as e:
                        self.log_message(f"Token bilgisi alma hatası: {mint_address} - {e}")

                    token_symbol = "Bilinmeyen"
                    if token_info and isinstance(token_info, dict):
                        token_symbol = token_info.get('symbol', 'Bilinmeyen')

                    self.positions_table.insert(
                        "", "end",
                        text=mint_address,
                        values=(token_symbol, f"${position['buy_price']:.8f}", f"${current_price:.8f}",
                                f"{position['remaining_amount']:.4f}", f"%{profit_loss_pct:.2f}")
                    )
                except Exception as e:
                    self.log_message(f"Pozisyon yenileme hatası: {mint_address} - {e}")
        except Exception as e:
            self.log_message(f"Pozisyonları yenileme hatası: {e}")

    def close_selected_position(self):
        """Seçili pozisyonu kapatır"""
        selected = self.positions_table.selection()
        if not selected:
            return

        mint_address = self.positions_table.item(selected[0], "text")
        if mint_address in self.trade_bot.positions:
            async def close_position():
                await self.trade_bot.close_position_manually(mint_address)
            
            task = run_async(close_position(), root=self.root)
            if task:
                self.active_tasks.append(task)

    def save_bot_state(self):
        """Bot durumunu kaydeder"""
        try:
            if hasattr(self.trade_bot, 'save_state') and callable(self.trade_bot.save_state):
                async def save_state():
                    await self.trade_bot.save_state()
                
                task = run_async(save_state(), root=self.root)
                if task:
                    self.active_tasks.append(task)
                self.log_message("✅ Bot durumu kaydedildi")
            else:
                self.log_message("❌ Durum kaydetme fonksiyonu bulunamadı")
        except Exception as e:
            self.log_message(f"Durum kaydetme hatası: {e}")

    def load_bot_state(self):
        """Bot durumunu yükler"""
        try:
            if hasattr(self.trade_bot, 'load_state') and callable(self.trade_bot.load_state):
                async def load_state():
                    await self.trade_bot.load_state()
                
                task = run_async(load_state(), root=self.root)
                if task:
                    self.active_tasks.append(task)
                self.log_message("✅ Bot durumu yüklendi")
            else:
                self.log_message("❌ Durum yükleme fonksiyonu bulunamadı")
        except Exception as e:
            self.log_message(f"Durum yükleme hatası: {e}")

    def show_manual_buy_dialog(self):
        """Manuel alım işlemi için diyalog gösterir"""
        from tkinter import simpledialog
        mint_address = simpledialog.askstring("Manuel Alım", "Token Mint Adresi:")
        if mint_address:
            try:
                amount = simpledialog.askfloat("Manuel Alım", "Alım Miktarı (SOL):", minvalue=0.01, maxvalue=100)
                if amount:
                    async def buy_token():
                        await self.trade_bot.buy(mint_address, amount, manual=True)
                    
                    task = run_async(buy_token(), root=self.root)
                    if task:
                        self.active_tasks.append(task)
            except Exception as e:
                self.log_message(f"Manuel alım hatası: {e}")

    def show_manual_sell_dialog(self):
        """Manuel satım işlemi için diyalog gösterir"""
        from tkinter import simpledialog, messagebox
        if not self.trade_bot.positions:
            messagebox.showinfo("Bilgi", "Satılacak pozisyon bulunmuyor.")
            return

        positions = list(self.trade_bot.positions.keys())
        position_str = simpledialog.askstring(
            "Manuel Satım",
            "Pozisyon Mint Adresi:\n" + "\n".join(positions)
        )

        if position_str and position_str in self.trade_bot.positions:
            try:
                async def sell_token():
                    await self.trade_bot.close_position_manually(position_str)
                
                task = run_async(sell_token(), root=self.root)
                if task:
                    self.active_tasks.append(task)
            except Exception as e:
                self.log_message(f"Manuel satım hatası: {e}")

    def save_settings(self):
        """Ayarları kaydeder"""
        try:
            trade_settings["buy_amount_sol"] = float(self.buy_amount_var.get())
            trade_settings["min_liquidity_usd"] = float(self.min_liquidity_var.get())
            trade_settings["max_positions"] = int(self.max_positions_var.get())
            trade_settings["min_balance_sol"] = float(self.min_balance_var.get())
            trade_settings["max_portfolio_loss"] = float(self.max_loss_var.get())
            trade_settings["trailing_stop_loss"] = float(self.trailing_sl_var.get())

            trade_settings["momentum_enabled"] = self.momentum_var.get()
            trade_settings["dip_buy_enabled"] = self.dip_buy_var.get()
            trade_settings["micro_pump_detection_enabled"] = self.micro_pump_var.get()
            trade_settings["liquidity_exit_enabled"] = self.liquidity_exit_var.get()
            trade_settings["whale_dump_detection_enabled"] = self.whale_dump_var.get()
            trade_settings["volume_drop_detection_enabled"] = self.volume_drop_var.get()
            trade_settings["token_diversification_enabled"] = self.diversification_var.get()
            trade_settings["night_mode_enabled"] = self.night_mode_var.get()
            trade_settings["sniping_enabled"] = self.sniping_var.get()
            trade_settings["rapid_cycle_enabled"] = self.rapid_cycle_var.get()
            trade_settings["auto_slippage_adjust"] = self.auto_slippage_var.get()
            trade_settings["gas_fee_optimization"] = self.gas_optimization_var.get()
            trade_settings["volatility_trading_enabled"] = self.volatility_var.get()
            trade_settings["price_deviation_enabled"] = self.price_deviation_var.get()
            trade_settings["ai_enabled"] = self.pump_detection_var.get()
            trade_settings["ai_pump_duration_prediction_enabled"] = self.duration_prediction_var.get()
            trade_settings["ai_confidence_threshold"] = float(self.confidence_var.get())

            self.log_message("✅ Ayarlar başarıyla kaydedildi!")
            
            if hasattr(self.trade_bot, 'save_state') and callable(self.trade_bot.save_state):
                async def save_state():
                    await self.trade_bot.save_state()
                
                task = run_async(save_state(), root=self.root)
                if task:
                    self.active_tasks.append(task)
        except ValueError as e:
            self.log_message(f"❌ Ayar kaydetme hatası: Geçersiz bir değer girdiniz - {e}")
        except Exception as e:
            self.log_message(f"❌ Ayar kaydetme hatası: {e}")

    def update_strategy(self):
        """Strateji profilini günceller"""
        try:
            import sys
            this_module = sys.modules['gotnw_tradebot.config']
            selected_strategy = self.strategy_var.get()
            
            # Modül düzeyinde değişkeni güncelle
            this_module.current_strategy = selected_strategy

            from gotnw_tradebot.config import STRATEGY_PROFILES
            if selected_strategy in STRATEGY_PROFILES:
                strategy_settings = STRATEGY_PROFILES[selected_strategy]
                trade_settings.update(strategy_settings)
                self.log_message(f"✅ Strateji profili '{selected_strategy}' olarak değiştirildi")
                
                # Trailing stop-loss değerini güncelle
                if hasattr(self, 'trailing_sl_var') and 'trailing_stop_loss' in trade_settings:
                    self.trailing_sl_var.set(str(trade_settings["trailing_stop_loss"]))
        except Exception as e:
            self.log_message(f"❌ Strateji güncelleme hatası: {str(e)}")
            import traceback
            traceback.print_exc()

    def add_tp_level(self):
        """Yeni bir take profit seviyesi ekler"""
        from tkinter import simpledialog
        profit = simpledialog.askfloat("Take Profit", "Kâr Yüzdesi (%):", minvalue=1, maxvalue=1000)
        if profit:
            sell_percentage = simpledialog.askfloat("Take Profit", "Satış Yüzdesi (%):", minvalue=1, maxvalue=100)
            if sell_percentage:
                id = len(self.tp_table.get_children()) + 1
                self.tp_table.insert("", "end", text=str(id), values=(profit, sell_percentage))

    def edit_tp_level(self):
        """Seçili take profit seviyesini düzenler"""
        selected = self.tp_table.selection()
        if not selected:
            return

        from tkinter import simpledialog
        current = self.tp_table.item(selected[0])
        id = current["text"]
        current_values = current["values"]

        profit = simpledialog.askfloat(
            "Take Profit", "Kâr Yüzdesi (%):",
            initialvalue=current_values[0], minvalue=1, maxvalue=1000
        )
        if profit:
            sell_percentage = simpledialog.askfloat(
                "Take Profit", "Satış Yüzdesi (%):",
                initialvalue=current_values[1], minvalue=1, maxvalue=100
            )
            if sell_percentage:
                self.tp_table.item(selected[0], values=(profit, sell_percentage))

    def delete_tp_level(self):
        """Seçili take profit seviyesini siler"""
        selected = self.tp_table.selection()
        if selected:
            self.tp_table.delete(selected[0])

    def add_sl_level(self):
        """Yeni bir stop loss seviyesi ekler"""
        from tkinter import simpledialog
        loss = simpledialog.askfloat("Stop Loss", "Zarar Yüzdesi (%):", minvalue=-100, maxvalue=0)
        if loss is not None:
            sell_percentage = simpledialog.askfloat("Stop Loss", "Satış Yüzdesi (%):", minvalue=1, maxvalue=100)
            if sell_percentage:
                id = len(self.sl_table.get_children()) + 1
                self.sl_table.insert("", "end", text=str(id), values=(loss, sell_percentage))

    def edit_sl_level(self):
        """Seçili stop loss seviyesini düzenler"""
        selected = self.sl_table.selection()
        if not selected:
            return

        from tkinter import simpledialog
        current = self.sl_table.item(selected[0])
        id = current["text"]
        current_values = current["values"]

        loss = simpledialog.askfloat(
            "Stop Loss", "Zarar Yüzdesi (%):",
            initialvalue=current_values[0], minvalue=-100, maxvalue=0
        )
        if loss is not None:
            sell_percentage = simpledialog.askfloat(
                "Stop Loss", "Satış Yüzdesi (%):",
                initialvalue=current_values[1], minvalue=1, maxvalue=100
            )
            if sell_percentage:
                self.sl_table.item(selected[0], values=(loss, sell_percentage))

    def delete_sl_level(self):
        """Seçili stop loss seviyesini siler"""
        selected = self.sl_table.selection()
        if selected:
            self.sl_table.delete(selected[0])

    def connect_wallet(self):
        """Cüzdan bağlama fonksiyonu"""
        private_key = self.private_key_entry.get().strip()
        if not private_key:
            return

        self.private_key_entry.delete(0, "end")

        async def connect_and_update():
            result = await self.wallet_manager.connect_wallet(private_key)
            self.log_message(result)
            self.update_wallet_list()

        task = run_async(connect_and_update(), root=self.root)
        if task:
            self.active_tasks.append(task)

    def update_wallet_list(self):
        """Cüzdan listesini günceller"""
        wallets = self.wallet_manager.wallets
        wallet_addresses = []

        for i, wallet in enumerate(wallets):
            address = str(wallet["keypair"].pubkey())
            wallet_addresses.append(f"{i+1}: {address}")

        self.wallets_combo["values"] = wallet_addresses

        if self.wallet_manager.active_wallet_index >= 0 and wallet_addresses:
            self.wallets_combo.current(self.wallet_manager.active_wallet_index)

    def switch_wallet(self):
        """Seçili cüzdana geçiş yapar"""
        if not self.wallets_combo.get():
            return

        try:
            selected = self.wallets_combo.get().split(":")[0].strip()
            index = int(selected) - 1

            async def switch_and_update():
                result = await self.wallet_manager.switch_wallet(index)
                self.log_message(result)

            task = run_async(switch_and_update(), root=self.root)
            if task:
                self.active_tasks.append(task)
        except Exception as e:
            self.log_message(f"Cüzdan değiştirme hatası: {e}")

    def add_token_to_watch(self):
        """İzleme listesine token ekler"""
        mint_address = self.token_entry.get().strip()
        if not mint_address:
            self.log_message("❌ Geçerli bir mint adresi girin")
            return

        self.log_message(f"🔍 Token izlemeye ekleniyor: {mint_address}")
        print(f"Token izlemeye ekleniyor: {mint_address}")
        
        async def add_token_async():
            try:
                print(f"WebSocket tokeni ekleniyor: {mint_address}")
                await self.trade_bot.add_websocket_token(mint_address)
                print(f"Token başarıyla eklendi, liste yenileniyor")
                # Burası kritik - GUI thread üzerinde çalışması gereken kod
                self.root.after(0, lambda: self._safe_refresh_tokens(mint_address))
            except Exception as e:
                print(f"Token ekleme hatası: {e}")
                self.log_message(f"❌ Token ekleme hatası: {str(e)}")
        
        import asyncio
        task = asyncio.create_task(add_token_async())
        self.active_tasks.append(task)

    def _safe_refresh_tokens(self, mint_address=None):
        """Tokenleri güvenli bir şekilde yeniler"""
        try:
            print("İzlenen tokenler yenileniyor...")
            self.refresh_watched_tokens()
            if mint_address:
                self.log_message(f"✅ Token başarıyla eklendi ve yenilendi: {mint_address}")
        except Exception as e:
            print(f"Token yenileme hatası: {e}")
            self.log_message("❌ Token listesi yenileme hatası")

    def refresh_watched_tokens(self):
        """İzlenen tokenler listesini günceller"""
        try:
            print("Watched tokens tablosu temizleniyor...")
            for i in self.watched_tokens_table.get_children():
                self.watched_tokens_table.delete(i)

            print(f"Trade bot subscribed_tokens: {self.trade_bot.subscribed_tokens}")
            for mint_address in self.trade_bot.subscribed_tokens:
                try:
                    print(f"Token bilgisi alınıyor: {mint_address}")
                    
                    # Asenkron işlem gerektirdiği için farklı bir yaklaşım gerektiriyor
                    async def fetch_and_display(mint_addr):
                        try:
                            token_info = await self.trade_bot.get_token_info(mint_addr)
                            if token_info:
                                price = token_info["price_usd"]
                                liquidity = token_info.get("liquidity_usd", 0)
                                volume = token_info.get("volume", 0)
                                symbol = token_info.get("symbol", "Bilinmeyen")

                                first_seen = "Bilinmiyor"
                                if mint_addr in self.trade_bot.first_seen_mints:
                                    first_seen = self.trade_bot.first_seen_mints[mint_addr].strftime("%Y-%m-%d %H:%M")

                                # GUI thread güvenli şekilde tabloya ekle
                                def add_to_table():
                                    try:
                                        self.watched_tokens_table.insert(
                                            "", "end",
                                            text=mint_addr,
                                            values=(symbol, f"${price:.8f}", f"${liquidity:.2f}", f"${volume:.2f}", first_seen)
                                        )
                                        print(f"Token tabloya eklendi: {mint_addr} ({symbol})")
                                    except Exception as e:
                                        print(f"Token tabloya eklenirken hata: {e}")
                                        
                                self.root.after(0, add_to_table)
                        except Exception as e:
                            print(f"Token bilgisi işlenirken hata: {e}")
                    
                    # Asenkron işlemi başlat ama bekleme
                    import asyncio
                    task = asyncio.create_task(fetch_and_display(mint_address))
                    self.active_tasks.append(task)
                    
                except Exception as e:
                    print(f"Token işleme hatası: {mint_address} - {e}")
        except Exception as e:
            print(f"Watched tokens yenileme hatası: {e}")
            import traceback
            traceback.print_exc()

    def remove_watched_token(self):
        """Seçili tokeni izleme listesinden kaldırır"""
        selected = self.watched_tokens_table.selection()
        if not selected:
            return

        mint_address = self.watched_tokens_table.item(selected[0], "text")
        if mint_address == "So11111111111111111111111111111111111111112":
            self.log_message("SOL tokenini izlemeden kaldıramazsınız.")
            return

        if mint_address in self.trade_bot.subscribed_tokens:
            self.trade_bot.subscribed_tokens.remove(mint_address)
            self.log_message(f"Token izlemeden kaldırıldı: {mint_address}")
            self.refresh_watched_tokens()

    def buy_selected_token(self):
        """Seçili tokeni satın alır"""
        selected = self.watched_tokens_table.selection()
        if not selected:
            return

        mint_address = self.watched_tokens_table.item(selected[0], "text")
        from tkinter import simpledialog
        amount = simpledialog.askfloat(
            "Token Satın Al", "Satın alma miktarı (SOL):",
            minvalue=0.01, maxvalue=100, initialvalue=trade_settings["buy_amount_sol"]
        )

        if amount:
            async def buy_token():
                await self.trade_bot.buy(mint_address, amount, manual=True)
            
            task = run_async(buy_token(), root=self.root)
            if task:
                self.active_tasks.append(task)

    def analyze_selected_token(self):
        """Seçili tokeni analiz eder"""
        selected = self.watched_tokens_table.selection()
        if not selected:
            return

        mint_address = self.watched_tokens_table.item(selected[0], "text")
        from tkinter import scrolledtext, Toplevel

        analysis_window = Toplevel(self.root)
        analysis_window.title(f"Token Analizi: {mint_address}")
        analysis_window.geometry("800x600")

        analysis_text = scrolledtext.ScrolledText(analysis_window, wrap="word")
        analysis_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        analysis_text.insert("1.0", "Analiz yapılıyor...\n\nLütfen bekleyin...")
        analysis_text.config(state="disabled")
        
        async def analyze_and_show():
            try:
                analysis = self.trade_bot.analyzer.analyze_token(mint_address)
                
                if analysis_window.winfo_exists():
                    analysis_text.config(state="normal")
                    analysis_text.delete("1.0", tk.END)
                    analysis_text.insert("1.0", analysis)
                    analysis_text.config(state="disabled")
            except Exception as e:
                if analysis_window.winfo_exists():
                    analysis_text.config(state="normal")
                    analysis_text.delete("1.0", tk.END)
                    analysis_text.insert("1.0", f"Analiz hatası: {e}")
                    analysis_text.config(state="disabled")
        
        task = run_async(analyze_and_show(), root=self.root)
        if task:
            self.active_tasks.append(task)

    def refresh_trade_history(self):
        """İşlem geçmişini günceller"""
        for i in self.history_table.get_children():
            self.history_table.delete(i)

        for trade in self.trade_bot.past_trades:
            try:
                mint_address = trade["mint"]
                timestamp = trade["timestamp"]

                if isinstance(timestamp, str):
                    try:
                        timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        timestamp = datetime.fromisoformat(timestamp)

                date_str = timestamp.strftime("%Y-%m-%d %H:%M")
                trade_type = "Alım" if trade.get("buy_price", 0) < trade.get("sell_price", 0) else "Satım"
                symbol = trade.get("symbol", "Bilinmeyen")
                price = trade.get("sell_price", 0)
                amount = trade.get("amount", 0)
                profit_loss = trade.get("profit_loss", 0)
                profit_loss_str = f"+{profit_loss:.4f} SOL" if profit_loss > 0 else f"{profit_loss:.4f} SOL"

                self.history_table.insert(
                    "", "end",
                    text=mint_address,
                    values=(date_str, trade_type, symbol, f"${price:.8f}", f"{amount:.4f}", profit_loss_str)
                )
            except Exception as e:
                self.log_message(f"İşlem geçmişi güncelleme hatası: {e}")

        self.update_trade_statistics()

    def update_trade_statistics(self):
        """İşlem istatistiklerini günceller"""
        trades = self.trade_bot.past_trades
        total_trades = len(trades)
        profitable_trades = sum(1 for t in trades if t.get("profit_loss", 0) > 0)

        success_rate = 0
        if total_trades > 0:
            success_rate = (profitable_trades / total_trades) * 100

        total_profit = sum(t.get("profit_loss", 0) for t in trades)
        profitable = [t.get("profit_loss", 0) for t in trades if t.get("profit_loss", 0) > 0]
        lossy = [t.get("profit_loss", 0) for t in trades if t.get("profit_loss", 0) < 0]

        avg_profit = sum(profitable) / len(profitable) if profitable else 0
        avg_loss = sum(lossy) / len(lossy) if lossy else 0

        self.total_trades_label.config(text=str(total_trades))
        self.profitable_trades_label.config(text=str(profitable_trades))
        self.success_rate_label.config(text=f"%{success_rate:.2f}")
        self.total_profit_label.config(text=f"{total_profit:.4f} SOL")
        self.avg_profit_label.config(text=f"{avg_profit:.4f} SOL")
        self.avg_loss_label.config(text=f"{avg_loss:.4f} SOL")

        self.ax.clear()
        if trades:
            sorted_trades = sorted(trades, key=lambda t: t.get("timestamp", 0))
            dates = [t.get("timestamp") for t in sorted_trades]
            profits = [t.get("profit_loss", 0) for t in sorted_trades]

            cumulative_profit = []
            current_profit = 0
            for p in profits:
                current_profit += p
                cumulative_profit.append(current_profit)

            self.ax.plot(dates, cumulative_profit, 'b-', marker='o')
            self.ax.set_title('Kümülatif Kâr/Zarar (SOL)')
            self.ax.set_xlabel('Tarih')
            self.ax.set_ylabel('Kâr/Zarar (SOL)')
            self.ax.grid(True)

            import matplotlib.dates as mdates
            self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
            self.ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))

            for label in (self.ax.get_xticklabels() + self.ax.get_yticklabels()):
                label.set_fontsize(8)

            self.ax.title.set_fontsize(10)
            self.figure.tight_layout()
            self.canvas.draw()

    def export_trade_history(self):
        """İşlem geçmişini CSV dosyasına aktarır"""
        from tkinter import filedialog
        import csv
        from datetime import datetime

        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"trade_history_{datetime.now().strftime('%Y%m%d')}.csv"
        )

        if not filepath:
            return

        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Tarih", "İşlem Türü", "Mint Adresi", "Token", "Fiyat", "Miktar", "Kâr/Zarar"])

                for trade in self.trade_bot.past_trades:
                    timestamp = trade.get("timestamp")
                    if isinstance(timestamp, datetime):
                        date_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        date_str = str(timestamp)

                    trade_type = "Alım" if trade.get("buy_price", 0) < trade.get("sell_price", 0) else "Satım"
                    mint_address = trade.get("mint", "")
                    symbol = trade.get("symbol", "Bilinmeyen")
                    price = trade.get("sell_price", 0)
                    amount = trade.get("amount", 0)
                    profit_loss = trade.get("profit_loss", 0)

                    writer.writerow([date_str, trade_type, mint_address, symbol, price, amount, profit_loss])

            self.log_message(f"✅ İşlem geçmişi dışa aktarıldı: {filepath}")
        except Exception as e:
            self.log_message(f"❌ İşlem geçmişi dışa aktarma hatası: {e}")

    def show_message(self, title, message, message_type="info"):
        """Mesaj kutusu gösterir"""
        from tkinter import messagebox

        if message_type == "info":
            messagebox.showinfo(title, message)
        elif message_type == "warning":
            messagebox.showwarning(title, message)
        elif message_type == "error":
            messagebox.showerror(title, message)


def start_gui(trade_bot):
    """
    GUI'yi başlatan fonksiyon
    
    Args:
        trade_bot: TradeBot örneği
    """
    root = tk.Tk()
    root.title("GOTNW TradeBot")
    root.geometry("1200x800")
    
    # Stil ayarları
    style = ttk.Style()
    
    # Temayı ayarla
    try:
        style.theme_use("clam")  # clam, alt, default, classic
    except tk.TclError:
        pass  # Tema yoksa devam et
    
    # Başlık renkleri
    style.configure("TLabelframe.Label", foreground="#0066cc", font=('TkDefaultFont', 10, 'bold'))
    
    # Buton stilleri
    style.configure("TButton", font=('TkDefaultFont', 9))
    style.configure("Primary.TButton", background="#0066cc", foreground="white")
    
    # Tablo stilleri
    style.configure("Treeview", font=('TkDefaultFont', 9))
    style.configure("Treeview.Heading", font=('TkDefaultFont', 9, 'bold'))
    
    app = TradeBotGUI(root, trade_bot)
    
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    root.mainloop()
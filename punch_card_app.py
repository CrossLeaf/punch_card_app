import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import requests
import json
import threading
import time
from datetime import datetime, timedelta
import os
import logging
from logging.handlers import RotatingFileHandler


class PunchCardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("自動打卡系統")
        self.root.geometry("700x600")

        # 設定日誌系統
        self.setup_logging()

        # 設定檔案
        self.config_file = "punch_config.json"
        self.load_config()

        # 打卡記錄
        self.punch_records = []

        self.setup_ui()
        self.start_scheduler()

        self.logger.info("應用程式啟動成功")

    def setup_logging(self):
        """設定日誌系統"""
        # 建立 logs 資料夾
        if not os.path.exists('logs'):
            os.makedirs('logs')

        # 設定日誌格式
        log_format = '%(asctime)s - %(levelname)s - %(message)s'

        # 設定主要 logger
        self.logger = logging.getLogger('PunchCardApp')
        self.logger.setLevel(logging.DEBUG)

        # 清除現有的 handlers
        self.logger.handlers.clear()

        # 檔案處理器 - 輪轉日誌檔案
        file_handler = RotatingFileHandler(
            'logs/punch_card.log',
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(log_format)
        file_handler.setFormatter(file_formatter)

        # 控制台處理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(log_format)
        console_handler.setFormatter(console_formatter)

        # 加入處理器
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def load_config(self):
        """載入設定檔"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.webhook_url = config.get('webhook_url', '')
                    self.punch_in_time = config.get('punch_in_time', '09:00')
                    self.punch_out_time = config.get('punch_out_time', '18:00')
                    self.logger.info(f"設定檔載入成功: {self.config_file}")
            else:
                self.webhook_url = ''
                self.punch_in_time = '09:00'
                self.punch_out_time = '18:00'
                self.logger.info("使用預設設定")
        except Exception as e:
            self.logger.error(f"載入設定失敗: {e}")
            self.webhook_url = ''
            self.punch_in_time = '09:00'
            self.punch_out_time = '18:00'

    def save_config(self):
        """儲存設定檔"""
        config = {
            'webhook_url': self.webhook_url,
            'punch_in_time': self.punch_in_time,
            'punch_out_time': self.punch_out_time
        }
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            self.logger.info("設定檔儲存成功")
        except Exception as e:
            self.logger.error(f"儲存設定失敗: {e}")
            messagebox.showerror("錯誤", f"儲存設定失敗: {e}")

    def setup_ui(self):
        """設置使用者介面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Webhook URL 設定
        ttk.Label(main_frame, text="Webhook URL:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.url_var = tk.StringVar(value=self.webhook_url)
        url_entry = ttk.Entry(main_frame, textvariable=self.url_var, width=60)
        url_entry.grid(row=0, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)

        # 時間設定
        ttk.Label(main_frame, text="上班打卡時間:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.punch_in_var = tk.StringVar(value=self.punch_in_time)
        ttk.Entry(main_frame, textvariable=self.punch_in_var, width=10).grid(row=1, column=1, sticky=tk.W, pady=5)

        ttk.Label(main_frame, text="下班打卡時間:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.punch_out_var = tk.StringVar(value=self.punch_out_time)
        ttk.Entry(main_frame, textvariable=self.punch_out_var, width=10).grid(row=2, column=1, sticky=tk.W, pady=5)

        # 按鈕
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=20)

        ttk.Button(button_frame, text="儲存設定", command=self.save_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="測試 Webhook", command=self.test_webhook).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="手動打卡", command=self.manual_punch).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="查看日誌", command=self.show_logs).pack(side=tk.LEFT, padx=5)

        # 今日打卡狀態
        status_frame = ttk.LabelFrame(main_frame, text="今日打卡狀態", padding="10")
        status_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)

        self.status_text = tk.Text(status_frame, height=8, width=70)
        scrollbar = ttk.Scrollbar(status_frame, orient="vertical", command=self.status_text.yview)
        self.status_text.configure(yscrollcommand=scrollbar.set)

        self.status_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # 系統狀態
        self.system_status = ttk.Label(main_frame, text="系統狀態: 運行中", foreground="green")
        self.system_status.grid(row=5, column=0, columnspan=3, pady=10)

        # 更新狀態顯示
        self.update_status_display()

    def save_settings(self):
        """儲存設定"""
        old_webhook = self.webhook_url
        old_punch_in = self.punch_in_time
        old_punch_out = self.punch_out_time

        self.webhook_url = self.url_var.get()
        self.punch_in_time = self.punch_in_var.get()
        self.punch_out_time = self.punch_out_var.get()

        self.logger.info(f"設定變更: Webhook URL: {old_webhook} -> {self.webhook_url}")
        self.logger.info(f"設定變更: 上班時間: {old_punch_in} -> {self.punch_in_time}")
        self.logger.info(f"設定變更: 下班時間: {old_punch_out} -> {self.punch_out_time}")

        if not self.webhook_url:
            self.logger.warning("Webhook URL 為空")
            messagebox.showwarning("警告", "請輸入 Webhook URL")
            return

        # 驗證時間格式
        try:
            datetime.strptime(self.punch_in_time, '%H:%M')
            datetime.strptime(self.punch_out_time, '%H:%M')
        except ValueError as e:
            self.logger.error(f"時間格式錯誤: {e}")
            messagebox.showerror("錯誤", "時間格式錯誤，請使用 HH:MM 格式")
            return

        self.save_config()
        messagebox.showinfo("成功", "設定已儲存")

    def test_webhook(self):
        """測試 Webhook"""
        if not self.webhook_url:
            self.logger.warning("嘗試測試 Webhook 但 URL 為空")
            messagebox.showwarning("警告", "請先設定 Webhook URL")
            return

        self.logger.info(f"開始測試 Webhook: {self.webhook_url}")

        try:
            response = self.send_webhook("測試打卡", detailed_log=True)
            if response:
                self.logger.info(f"Webhook 測試成功 - 狀態碼: {response.status_code}")
                messagebox.showinfo("成功", f"Webhook 測試成功\n狀態碼: {response.status_code}")
            else:
                self.logger.error("Webhook 測試失敗 - 無回應")
                messagebox.showerror("失敗", "Webhook 測試失敗 - 請查看日誌了解詳細錯誤")
        except Exception as e:
            self.logger.error(f"測試 Webhook 時發生異常: {e}")
            messagebox.showerror("錯誤", f"測試失敗: {e}\n請查看日誌了解詳細錯誤")

    def manual_punch(self):
        """手動打卡"""
        if not self.webhook_url:
            self.logger.warning("嘗試手動打卡但 Webhook URL 為空")
            messagebox.showwarning("警告", "請先設定 Webhook URL")
            return

        self.logger.info("開始手動打卡")

        try:
            current_time = datetime.now()
            response = self.send_webhook("手動打卡", detailed_log=True)

            if response and response.status_code == 200:
                record = f"{current_time.strftime('%H:%M:%S')} - 手動打卡成功"
                self.punch_records.append(record)
                self.update_status_display()
                self.logger.info("手動打卡成功")
                messagebox.showinfo("成功", "手動打卡成功")
            else:
                record = f"{current_time.strftime('%H:%M:%S')} - 手動打卡失敗"
                self.punch_records.append(record)
                self.update_status_display()
                self.logger.error(f"手動打卡失敗 - 狀態碼: {response.status_code if response else 'None'}")
                messagebox.showerror("失敗", "手動打卡失敗 - 請查看日誌了解詳細錯誤")
        except Exception as e:
            current_time = datetime.now()
            record = f"{current_time.strftime('%H:%M:%S')} - 手動打卡錯誤"
            self.punch_records.append(record)
            self.update_status_display()
            self.logger.error(f"手動打卡時發生異常: {e}")
            messagebox.showerror("錯誤", f"手動打卡失敗: {e}\n請查看日誌了解詳細錯誤")

    def send_webhook(self, punch_type, detailed_log=False):
        """發送 Webhook 請求"""
        try:
            data = {
                "type": punch_type,
                "timestamp": datetime.now().isoformat(),
                "message": f"自動打卡系統 - {punch_type}"
            }

            if detailed_log:
                self.logger.debug(f"準備發送 Webhook 請求:")
                self.logger.debug(f"  URL: {self.webhook_url}")
                self.logger.debug(f"  資料: {json.dumps(data, ensure_ascii=False, indent=2)}")

            response = requests.post(
                self.webhook_url,
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )

            if detailed_log:
                self.logger.debug(f"收到回應:")
                self.logger.debug(f"  狀態碼: {response.status_code}")
                self.logger.debug(f"  回應標頭: {dict(response.headers)}")
                self.logger.debug(f"  回應內容: {response.text}")

            if response.status_code == 200:
                self.logger.info(f"Webhook 請求成功 - {punch_type}")
            else:
                self.logger.warning(
                    f"Webhook 請求失敗 - {punch_type}, 狀態碼: {response.status_code}, 回應: {response.text}")

            return response

        except requests.exceptions.Timeout as e:
            self.logger.error(f"Webhook 請求超時: {e}")
            return None
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"Webhook 連線錯誤: {e}")
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Webhook 請求錯誤: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Webhook 發送時發生未知錯誤: {e}")
            return None

    def start_scheduler(self):
        """啟動排程器"""

        def scheduler():
            self.logger.info("排程器啟動")
            while True:
                try:
                    current_time = datetime.now()
                    current_time_str = current_time.strftime('%H:%M')

                    # 檢查是否需要打卡
                    if current_time_str == self.punch_in_time:
                        self.logger.info(f"觸發上班打卡時間: {current_time_str}")
                        self.auto_punch("上班打卡")
                    elif current_time_str == self.punch_out_time:
                        self.logger.info(f"觸發下班打卡時間: {current_time_str}")
                        self.auto_punch("下班打卡")

                    time.sleep(60)  # 每分鐘檢查一次
                except Exception as e:
                    self.logger.error(f"排程器錯誤: {e}")
                    time.sleep(60)

        # 在背景執行排程器
        scheduler_thread = threading.Thread(target=scheduler, daemon=True)
        scheduler_thread.start()

    def auto_punch(self, punch_type):
        """自動打卡"""
        if not self.webhook_url:
            self.logger.warning(f"自動打卡失敗 - Webhook URL 為空: {punch_type}")
            return

        self.logger.info(f"開始自動打卡: {punch_type}")

        try:
            response = self.send_webhook(punch_type)
            current_time = datetime.now()

            if response and response.status_code == 200:
                record = f"{current_time.strftime('%H:%M:%S')} - {punch_type}成功"
                self.punch_records.append(record)
                self.logger.info(f"自動打卡成功: {punch_type}")
            else:
                record = f"{current_time.strftime('%H:%M:%S')} - {punch_type}失敗"
                self.punch_records.append(record)
                self.logger.error(f"自動打卡失敗: {punch_type}, 狀態碼: {response.status_code if response else 'None'}")

            # 更新 UI (需要在主執行緒中執行)
            self.root.after(0, self.update_status_display)

        except Exception as e:
            current_time = datetime.now()
            record = f"{current_time.strftime('%H:%M:%S')} - {punch_type}錯誤: {e}"
            self.punch_records.append(record)
            self.logger.error(f"自動打卡時發生異常: {punch_type}, 錯誤: {e}")
            self.root.after(0, self.update_status_display)

    def show_logs(self):
        """顯示日誌視窗"""
        log_window = tk.Toplevel(self.root)
        log_window.title("系統日誌")
        log_window.geometry("800x600")

        # 建立文字區域
        log_text = tk.Text(log_window, wrap=tk.WORD)
        log_scrollbar = ttk.Scrollbar(log_window, orient="vertical", command=log_text.yview)
        log_text.configure(yscrollcommand=log_scrollbar.set)

        log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 讀取並顯示日誌
        try:
            with open('logs/punch_card.log', 'r', encoding='utf-8') as f:
                log_content = f.read()
                log_text.insert(tk.END, log_content)
                log_text.see(tk.END)  # 捲動到底部
        except FileNotFoundError:
            log_text.insert(tk.END, "日誌檔案不存在")
        except Exception as e:
            log_text.insert(tk.END, f"讀取日誌檔案失敗: {e}")

    def update_status_display(self):
        """更新狀態顯示"""
        self.status_text.delete(1.0, tk.END)

        # 顯示今日日期
        today = datetime.now().strftime('%Y-%m-%d')
        self.status_text.insert(tk.END, f"今日日期: {today}\n")
        self.status_text.insert(tk.END, f"設定時間: 上班 {self.punch_in_time}, 下班 {self.punch_out_time}\n")
        self.status_text.insert(tk.END,
                                f"Webhook URL: {self.webhook_url[:50]}{'...' if len(self.webhook_url) > 50 else ''}\n")
        self.status_text.insert(tk.END, "-" * 50 + "\n")

        # 顯示今日打卡記錄
        if self.punch_records:
            self.status_text.insert(tk.END, "今日打卡記錄:\n")
            for record in self.punch_records[-10:]:  # 只顯示最近10筆記錄
                self.status_text.insert(tk.END, f"{record}\n")
        else:
            self.status_text.insert(tk.END, "今日尚未有打卡記錄\n")

        # 自動捲動到底部
        self.status_text.see(tk.END)


if __name__ == "__main__":
    root = tk.Tk()
    app = PunchCardApp(root)
    root.mainloop()

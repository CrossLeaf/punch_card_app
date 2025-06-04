import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import requests
import json
import threading
import time
from datetime import datetime, timedelta
import os


class PunchCardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("自動打卡系統")
        self.root.geometry("600x500")

        # 設定檔案
        self.config_file = "punch_config.json"
        self.load_config()

        # 打卡記錄
        self.punch_records = []

        self.setup_ui()
        self.start_scheduler()

    def load_config(self):
        """載入設定檔"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.webhook_url = config.get('webhook_url', '')
                    self.punch_in_time = config.get('punch_in_time', '09:00')
                    self.punch_out_time = config.get('punch_out_time', '18:00')
            else:
                self.webhook_url = ''
                self.punch_in_time = '09:00'
                self.punch_out_time = '18:00'
        except Exception as e:
            print(f"載入設定失敗: {e}")
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
        except Exception as e:
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
        self.webhook_url = self.url_var.get()
        self.punch_in_time = self.punch_in_var.get()
        self.punch_out_time = self.punch_out_var.get()

        if not self.webhook_url:
            messagebox.showwarning("警告", "請輸入 Webhook URL")
            return

        self.save_config()
        messagebox.showinfo("成功", "設定已儲存")

    def test_webhook(self):
        """測試 Webhook"""
        if not self.webhook_url:
            messagebox.showwarning("警告", "請先設定 Webhook URL")
            return

        try:
            response = self.send_webhook("測試打卡")
            if response:
                messagebox.showinfo("成功", f"Webhook 測試成功\n狀態碼: {response.status_code}")
            else:
                messagebox.showerror("失敗", "Webhook 測試失敗")
        except Exception as e:
            messagebox.showerror("錯誤", f"測試失敗: {e}")

    def manual_punch(self):
        """手動打卡"""
        if not self.webhook_url:
            messagebox.showwarning("警告", "請先設定 Webhook URL")
            return

        try:
            current_time = datetime.now()
            response = self.send_webhook("手動打卡")

            if response and response.status_code == 200:
                record = f"{current_time.strftime('%H:%M:%S')} - 手動打卡成功"
                self.punch_records.append(record)
                self.update_status_display()
                messagebox.showinfo("成功", "手動打卡成功")
            else:
                messagebox.showerror("失敗", "手動打卡失敗")
        except Exception as e:
            messagebox.showerror("錯誤", f"手動打卡失敗: {e}")

    def send_webhook(self, punch_type):
        """發送 Webhook 請求"""
        try:
            data = {
                "type": punch_type,
                "timestamp": datetime.now().isoformat(),
                "message": f"自動打卡系統 - {punch_type}"
            }

            response = requests.post(
                self.webhook_url,
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            return response
        except Exception as e:
            print(f"Webhook 發送失敗: {e}")
            return None

    def start_scheduler(self):
        """啟動排程器"""

        def scheduler():
            while True:
                try:
                    current_time = datetime.now()
                    current_time_str = current_time.strftime('%H:%M')

                    # 檢查是否需要打卡
                    if current_time_str == self.punch_in_time:
                        self.auto_punch("上班打卡")
                    elif current_time_str == self.punch_out_time:
                        self.auto_punch("下班打卡")

                    time.sleep(60)  # 每分鐘檢查一次
                except Exception as e:
                    print(f"排程器錯誤: {e}")
                    time.sleep(60)

        # 在背景執行排程器
        scheduler_thread = threading.Thread(target=scheduler, daemon=True)
        scheduler_thread.start()

    def auto_punch(self, punch_type):
        """自動打卡"""
        if not self.webhook_url:
            return

        try:
            response = self.send_webhook(punch_type)
            current_time = datetime.now()

            if response and response.status_code == 200:
                record = f"{current_time.strftime('%H:%M:%S')} - {punch_type}成功"
                self.punch_records.append(record)
            else:
                record = f"{current_time.strftime('%H:%M:%S')} - {punch_type}失敗"
                self.punch_records.append(record)

            # 更新 UI (需要在主執行緒中執行)
            self.root.after(0, self.update_status_display)

        except Exception as e:
            current_time = datetime.now()
            record = f"{current_time.strftime('%H:%M:%S')} - {punch_type}錯誤: {e}"
            self.punch_records.append(record)
            self.root.after(0, self.update_status_display)

    def update_status_display(self):
        """更新狀態顯示"""
        self.status_text.delete(1.0, tk.END)

        # 顯示今日日期
        today = datetime.now().strftime('%Y-%m-%d')
        self.status_text.insert(tk.END, f"今日日期: {today}\n")
        self.status_text.insert(tk.END, f"設定時間: 上班 {self.punch_in_time}, 下班 {self.punch_out_time}\n")
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

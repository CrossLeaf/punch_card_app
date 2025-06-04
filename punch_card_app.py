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
import random


class PunchCardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("自動打卡系統")
        self.root.geometry("800x700")

        # 設定日誌系統
        self.setup_logging()

        # 設定檔案
        self.config_file = "punch_config.json"
        self.load_config()

        # 打卡記錄
        self.punch_records = []

        # 隨機時間控制
        self.punch_in_random_time = None
        self.punch_out_random_time = None
        self.punch_in_executed = False
        self.punch_out_executed = False

        # 日期追蹤和自動打卡控制
        self.last_check_date = None
        self.auto_punch_enabled = True
        self.scheduler_running = False

        self.setup_ui()
        self.start_scheduler()

        self.logger.info("應用程式啟動成功")

    def start_scheduler(self):
        """啟動排程器"""
        if not self.scheduler_running:
            self.scheduler_running = True
            self.schedule_check()
            self.logger.info("排程器已啟動")

    def schedule_check(self):
        """定期檢查打卡時間"""
        if self.scheduler_running:
            self.check_punch_time()
            # 每10秒檢查一次
            self.root.after(10000, self.schedule_check)

    def check_punch_time(self):
        """檢查是否到了打卡時間"""
        if not self.auto_punch_enabled:
            return

        current_time = datetime.now()
        current_date = current_time.date()

        # 檢查是否需要重置每日執行狀態
        if not hasattr(self, 'last_check_date') or self.last_check_date != current_date:
            self.punch_in_executed = False
            self.punch_out_executed = False
            self.last_check_date = current_date
            self.logger.info(f"新的一天開始，重置打卡狀態: {current_date}")

            # 重新產生隨機時間
            self.generate_random_times()

        # 檢查上班打卡
        if not self.punch_in_executed:
            should_punch_in = False

            if self.punch_in_mode == "exact":
                target_time_str = self.punch_in_time
                try:
                    target_time = datetime.strptime(f"{current_date} {target_time_str}", '%Y-%m-%d %H:%M')

                    # 精確時間：當前時間在目標時間的15秒內（縮短時間窗口）
                    time_diff = abs((current_time - target_time).total_seconds())
                    if time_diff <= 15:
                        should_punch_in = True
                        self.logger.info(f"觸發上班精確打卡時間: {current_time.strftime('%H:%M:%S')}")
                except ValueError as e:
                    self.logger.error(f"上班精確時間格式錯誤: {e}")

            elif self.punch_in_mode == "random":
                if self.punch_in_random_time:
                    # 隨機時間：當前時間超過隨機時間且在30秒內（縮短時間窗口）
                    time_diff = (current_time - self.punch_in_random_time).total_seconds()
                    if 0 <= time_diff <= 30:  # 0到30秒內
                        should_punch_in = True
                        self.logger.info(
                            f"觸發上班隨機打卡時間: {current_time.strftime('%H:%M:%S')}, 目標時間: {self.punch_in_random_time.strftime('%H:%M:%S')}")

            if should_punch_in:
                self.punch_in_executed = True  # 立即設置為已執行，防止重複
                self.schedule_punch("上班打卡")

        # 檢查下班打卡
        if not self.punch_out_executed:
            should_punch_out = False

            if self.punch_out_mode == "exact":
                target_time_str = self.punch_out_time
                try:
                    target_time = datetime.strptime(f"{current_date} {target_time_str}", '%Y-%m-%d %H:%M')

                    # 精確時間：當前時間在目標時間的15秒內（縮短時間窗口）
                    time_diff = abs((current_time - target_time).total_seconds())
                    if time_diff <= 15:
                        should_punch_out = True
                        self.logger.info(f"觸發下班精確打卡時間: {current_time.strftime('%H:%M:%S')}")
                except ValueError as e:
                    self.logger.error(f"下班精確時間格式錯誤: {e}")

            elif self.punch_out_mode == "random":
                if self.punch_out_random_time:
                    # 隨機時間：當前時間超過隨機時間且在30秒內（縮短時間窗口）
                    time_diff = (current_time - self.punch_out_random_time).total_seconds()
                    if 0 <= time_diff <= 30:  # 0到30秒內
                        should_punch_out = True
                        self.logger.info(
                            f"觸發下班隨機打卡時間: {current_time.strftime('%H:%M:%S')}, 目標時間: {self.punch_out_random_time.strftime('%H:%M:%S')}")

            if should_punch_out:
                self.punch_out_executed = True  # 立即設置為已執行，防止重複
                self.schedule_punch("下班打卡")

    def schedule_punch(self, punch_type):
        """排程打卡執行"""

        def punch_task():
            try:
                current_time = datetime.now()
                self.logger.info(f"開始執行自動打卡: {punch_type}")

                response = self.send_webhook(punch_type)

                # 檢查回應狀態
                if response and 200 <= response.status_code < 300:
                    record = f"{current_time.strftime('%H:%M:%S')} - {punch_type}成功 (狀態碼: {response.status_code})"
                    self.punch_records.append(record)
                    self.logger.info(f"自動打卡成功: {punch_type}, 狀態碼: {response.status_code}")
                else:
                    status_code = response.status_code if response else "無回應"
                    record = f"{current_time.strftime('%H:%M:%S')} - {punch_type}失敗 (狀態碼: {status_code})"
                    self.punch_records.append(record)
                    self.logger.error(f"自動打卡失敗: {punch_type}, 狀態碼: {status_code}")

                # 更新 UI (需要在主執行緒中執行)
                self.root.after(0, self.update_status_display)

            except Exception as e:
                current_time = datetime.now()
                record = f"{current_time.strftime('%H:%M:%S')} - {punch_type}錯誤: {e}"
                self.punch_records.append(record)
                self.logger.error(f"自動打卡時發生異常: {punch_type}, 錯誤: {e}")
                self.root.after(0, self.update_status_display)

        # 在新執行緒中執行打卡
        threading.Thread(target=punch_task, daemon=True).start()

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

                    # 舊版相容性
                    self.punch_in_time = config.get('punch_in_time', '09:00')
                    self.punch_out_time = config.get('punch_out_time', '18:00')

                    # 新增時間區間設定
                    self.punch_in_start = config.get('punch_in_start', '09:00')
                    self.punch_in_end = config.get('punch_in_end', '09:20')
                    self.punch_out_start = config.get('punch_out_start', '18:00')
                    self.punch_out_end = config.get('punch_out_end', '18:20')

                    # 模式設定 (exact: 精確時間, random: 隨機區間)
                    self.punch_in_mode = config.get('punch_in_mode', 'exact')
                    self.punch_out_mode = config.get('punch_out_mode', 'exact')

                    self.logger.info(f"設定檔載入成功: {self.config_file}")
            else:
                self.set_default_config()
                self.logger.info("使用預設設定")
        except Exception as e:
            self.logger.error(f"載入設定失敗: {e}")
            self.set_default_config()

    def set_default_config(self):
        """設定預設值"""
        self.webhook_url = ''
        self.punch_in_time = '09:00'
        self.punch_out_time = '18:00'
        self.punch_in_start = '09:00'
        self.punch_in_end = '09:20'
        self.punch_out_start = '18:00'
        self.punch_out_end = '18:20'
        self.punch_in_mode = 'exact'
        self.punch_out_mode = 'exact'

    def save_config(self):
        """儲存設定檔"""
        config = {
            'webhook_url': self.webhook_url,
            'punch_in_time': self.punch_in_time,
            'punch_out_time': self.punch_out_time,
            'punch_in_start': self.punch_in_start,
            'punch_in_end': self.punch_in_end,
            'punch_out_start': self.punch_out_start,
            'punch_out_end': self.punch_out_end,
            'punch_in_mode': self.punch_in_mode,
            'punch_out_mode': self.punch_out_mode
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
        url_entry.grid(row=0, column=1, columnspan=4, sticky=(tk.W, tk.E), pady=5)

        # 上班打卡設定
        punch_in_frame = ttk.LabelFrame(main_frame, text="上班打卡設定", padding="10")
        punch_in_frame.grid(row=1, column=0, columnspan=5, sticky=(tk.W, tk.E), pady=10)

        self.punch_in_mode_var = tk.StringVar(value=self.punch_in_mode)
        ttk.Radiobutton(punch_in_frame, text="精確時間", variable=self.punch_in_mode_var,
                        value="exact", command=self.update_punch_in_mode).grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Radiobutton(punch_in_frame, text="隨機區間", variable=self.punch_in_mode_var,
                        value="random", command=self.update_punch_in_mode).grid(row=0, column=1, sticky=tk.W, padx=5)

        # 精確時間設定
        self.punch_in_exact_frame = ttk.Frame(punch_in_frame)
        self.punch_in_exact_frame.grid(row=1, column=0, columnspan=5, sticky=(tk.W, tk.E), pady=5)
        ttk.Label(self.punch_in_exact_frame, text="打卡時間:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.punch_in_time_var = tk.StringVar(value=self.punch_in_time)
        ttk.Entry(self.punch_in_exact_frame, textvariable=self.punch_in_time_var, width=10).grid(row=0, column=1,
                                                                                                 sticky=tk.W, padx=5)

        # 隨機區間設定
        self.punch_in_random_frame = ttk.Frame(punch_in_frame)
        self.punch_in_random_frame.grid(row=2, column=0, columnspan=5, sticky=(tk.W, tk.E), pady=5)
        ttk.Label(self.punch_in_random_frame, text="開始時間:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.punch_in_start_var = tk.StringVar(value=self.punch_in_start)
        ttk.Entry(self.punch_in_random_frame, textvariable=self.punch_in_start_var, width=10).grid(row=0, column=1,
                                                                                                   sticky=tk.W, padx=5)
        ttk.Label(self.punch_in_random_frame, text="結束時間:").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.punch_in_end_var = tk.StringVar(value=self.punch_in_end)
        ttk.Entry(self.punch_in_random_frame, textvariable=self.punch_in_end_var, width=10).grid(row=0, column=3,
                                                                                                 sticky=tk.W, padx=5)

        # 下班打卡設定
        punch_out_frame = ttk.LabelFrame(main_frame, text="下班打卡設定", padding="10")
        punch_out_frame.grid(row=2, column=0, columnspan=5, sticky=(tk.W, tk.E), pady=10)

        self.punch_out_mode_var = tk.StringVar(value=self.punch_out_mode)
        ttk.Radiobutton(punch_out_frame, text="精確時間", variable=self.punch_out_mode_var,
                        value="exact", command=self.update_punch_out_mode).grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Radiobutton(punch_out_frame, text="隨機區間", variable=self.punch_out_mode_var,
                        value="random", command=self.update_punch_out_mode).grid(row=0, column=1, sticky=tk.W, padx=5)

        # 精確時間設定
        self.punch_out_exact_frame = ttk.Frame(punch_out_frame)
        self.punch_out_exact_frame.grid(row=1, column=0, columnspan=5, sticky=(tk.W, tk.E), pady=5)
        ttk.Label(self.punch_out_exact_frame, text="打卡時間:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.punch_out_time_var = tk.StringVar(value=self.punch_out_time)
        ttk.Entry(self.punch_out_exact_frame, textvariable=self.punch_out_time_var, width=10).grid(row=0, column=1,
                                                                                                   sticky=tk.W, padx=5)

        # 隨機區間設定
        self.punch_out_random_frame = ttk.Frame(punch_out_frame)
        self.punch_out_random_frame.grid(row=2, column=0, columnspan=5, sticky=(tk.W, tk.E), pady=5)
        ttk.Label(self.punch_out_random_frame, text="開始時間:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.punch_out_start_var = tk.StringVar(value=self.punch_out_start)
        ttk.Entry(self.punch_out_random_frame, textvariable=self.punch_out_start_var, width=10).grid(row=0, column=1,
                                                                                                     sticky=tk.W,
                                                                                                     padx=5)
        ttk.Label(self.punch_out_random_frame, text="結束時間:").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.punch_out_end_var = tk.StringVar(value=self.punch_out_end)
        ttk.Entry(self.punch_out_random_frame, textvariable=self.punch_out_end_var, width=10).grid(row=0, column=3,
                                                                                                   sticky=tk.W, padx=5)

        # 按鈕
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=5, pady=20)

        ttk.Button(button_frame, text="儲存設定", command=self.save_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="測試 Webhook", command=self.test_webhook).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="手動打卡", command=self.manual_punch).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="查看日誌", command=self.show_logs).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="重置狀態", command=self.reset_punch_status).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="重新產生隨機時間", command=self.regenerate_random_times).pack(side=tk.LEFT,
                                                                                                     padx=5)

        # 今日打卡狀態
        status_frame = ttk.LabelFrame(main_frame, text="今日打卡狀態", padding="10")
        status_frame.grid(row=4, column=0, columnspan=5, sticky=(tk.W, tk.E), pady=10)

        self.status_text = tk.Text(status_frame, height=10, width=80)
        scrollbar = ttk.Scrollbar(status_frame, orient="vertical", command=self.status_text.yview)
        self.status_text.configure(yscrollcommand=scrollbar.set)

        self.status_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        # 系統狀態
        self.system_status = ttk.Label(main_frame, text="系統狀態: 運行中", foreground="green")
        self.system_status.grid(row=5, column=0, columnspan=5, pady=10)

        # 初始化 UI 狀態
        self.update_punch_in_mode()
        self.update_punch_out_mode()
        self.update_status_display()

    def update_punch_in_mode(self):
        """更新上班打卡模式顯示"""
        if self.punch_in_mode_var.get() == "exact":
            self.punch_in_exact_frame.grid()
            self.punch_in_random_frame.grid_remove()
        else:
            self.punch_in_exact_frame.grid_remove()
            self.punch_in_random_frame.grid()

    def update_punch_out_mode(self):
        """更新下班打卡模式顯示"""
        if self.punch_out_mode_var.get() == "exact":
            self.punch_out_exact_frame.grid()
            self.punch_out_random_frame.grid_remove()
        else:
            self.punch_out_exact_frame.grid_remove()
            self.punch_out_random_frame.grid()

    def save_settings(self):
        """儲存設定"""
        try:
            # 儲存基本設定
            self.webhook_url = self.url_var.get()
            self.punch_in_time = self.punch_in_time_var.get()
            self.punch_out_time = self.punch_out_time_var.get()
            self.punch_in_start = self.punch_in_start_var.get()
            self.punch_in_end = self.punch_in_end_var.get()
            self.punch_out_start = self.punch_out_start_var.get()
            self.punch_out_end = self.punch_out_end_var.get()
            self.punch_in_mode = self.punch_in_mode_var.get()
            self.punch_out_mode = self.punch_out_mode_var.get()

            if not self.webhook_url:
                self.logger.warning("Webhook URL 為空")
                messagebox.showwarning("警告", "請輸入 Webhook URL")
                return

            # 驗證時間格式
            self.validate_time_format(self.punch_in_time, "上班精確時間")
            self.validate_time_format(self.punch_out_time, "下班精確時間")
            self.validate_time_format(self.punch_in_start, "上班開始時間")
            self.validate_time_format(self.punch_in_end, "上班結束時間")
            self.validate_time_format(self.punch_out_start, "下班開始時間")
            self.validate_time_format(self.punch_out_end, "下班結束時間")

            # 驗證時間區間
            if self.punch_in_mode == "random":
                self.validate_time_range(self.punch_in_start, self.punch_in_end, "上班時間區間")
            if self.punch_out_mode == "random":
                self.validate_time_range(self.punch_out_start, self.punch_out_end, "下班時間區間")

            self.save_config()

            # 修改：暫停自動打卡，重新產生隨機時間，然後恢復
            was_enabled = self.auto_punch_enabled
            self.auto_punch_enabled = False  # 暫停自動打卡

            self.generate_random_times()

            # 延遲恢復自動打卡，避免立即觸發
            def restore_auto_punch():
                self.auto_punch_enabled = was_enabled
                self.logger.info("自動打卡功能已恢復")

            self.root.after(2000, restore_auto_punch)  # 2秒後恢復

            self.logger.info("設定儲存成功")
            messagebox.showinfo("成功", "設定已儲存")
            self.update_status_display()

        except ValueError as e:
            self.logger.error(f"設定驗證失敗: {e}")
            messagebox.showerror("錯誤", str(e))

    def validate_time_format(self, time_str, field_name):
        """驗證時間格式"""
        try:
            datetime.strptime(time_str, '%H:%M')
        except ValueError:
            raise ValueError(f"{field_name} 格式錯誤，請使用 HH:MM 格式")

    def validate_time_range(self, start_time, end_time, field_name):
        """驗證時間區間"""
        start = datetime.strptime(start_time, '%H:%M')
        end = datetime.strptime(end_time, '%H:%M')
        if start >= end:
            raise ValueError(f"{field_name} 錯誤：開始時間必須早於結束時間")

    def generate_random_times(self):
        """產生隨機打卡時間"""
        current_date = datetime.now().date()

        # 產生上班隨機時間
        if self.punch_in_mode == "random":
            try:
                start_time = datetime.strptime(f"{current_date} {self.punch_in_start}", '%Y-%m-%d %H:%M')
                end_time = datetime.strptime(f"{current_date} {self.punch_in_end}", '%Y-%m-%d %H:%M')

                time_diff = int((end_time - start_time).total_seconds())
                if time_diff > 0:
                    random_seconds = random.randint(0, time_diff)
                    self.punch_in_random_time = start_time + timedelta(seconds=random_seconds)
                    self.logger.info(f"產生上班隨機時間: {self.punch_in_random_time.strftime('%H:%M:%S')}")
                else:
                    self.logger.error("上班時間區間設定錯誤")
                    self.punch_in_random_time = None
            except ValueError as e:
                self.logger.error(f"產生上班隨機時間失敗: {e}")
                self.punch_in_random_time = None

        # 產生下班隨機時間
        if self.punch_out_mode == "random":
            try:
                start_time = datetime.strptime(f"{current_date} {self.punch_out_start}", '%Y-%m-%d %H:%M')
                end_time = datetime.strptime(f"{current_date} {self.punch_out_end}", '%Y-%m-%d %H:%M')

                time_diff = int((end_time - start_time).total_seconds())
                if time_diff > 0:
                    random_seconds = random.randint(0, time_diff)
                    self.punch_out_random_time = start_time + timedelta(seconds=random_seconds)
                    self.logger.info(f"產生下班隨機時間: {self.punch_out_random_time.strftime('%H:%M:%S')}")
                else:
                    self.logger.error("下班時間區間設定錯誤")
                    self.punch_out_random_time = None
            except ValueError as e:
                self.logger.error(f"產生下班隨機時間失敗: {e}")
                self.punch_out_random_time = None

    def get_random_time_in_range(self, start_time_str, end_time_str):
        """在指定時間範圍內產生隨機時間"""
        today = datetime.now().date()
        start_time = datetime.combine(today, datetime.strptime(start_time_str, '%H:%M').time())
        end_time = datetime.combine(today, datetime.strptime(end_time_str, '%H:%M').time())

        # 計算時間差（秒）
        time_diff = int((end_time - start_time).total_seconds())

        # 產生隨機秒數
        random_seconds = random.randint(0, time_diff)

        # 回傳隨機時間
        return start_time + timedelta(seconds=random_seconds)

    def regenerate_random_times(self):
        """重新產生隨機時間"""
        self.generate_random_times()
        self.update_status_display()
        messagebox.showinfo("成功", "隨機時間已重新產生")

    def manual_punch(self):
        """手動打卡"""
        punch_types = ["上班打卡", "下班打卡"]
        punch_type = simpledialog.askstring("手動打卡",
                                            f"請選擇打卡類型：\n1. {punch_types[0]}\n2. {punch_types[1]}\n請輸入 1 或 2：")

        if punch_type in ['1', '2']:
            selected_type = punch_types[int(punch_type) - 1]
            response = self.send_webhook(selected_type, detailed_log=True)

            if response and 200 <= response.status_code < 300:
                messagebox.showinfo("成功", f"{selected_type}成功！")
            else:
                messagebox.showerror("失敗", f"{selected_type}失敗！")

            self.update_status_display()

    def test_webhook(self):
        """測試 Webhook 連接"""
        if not self.webhook_url:
            messagebox.showwarning("警告", "請先設定 Webhook URL")
            return

        response = self.send_webhook("測試連接", detailed_log=True)

        if response and 200 <= response.status_code < 300:
            messagebox.showinfo("成功", f"Webhook 測試成功！\n狀態碼: {response.status_code}")
        else:
            status_code = response.status_code if response else "無回應"
            messagebox.showerror("失敗", f"Webhook 測試失敗！\n狀態碼: {status_code}")

    def send_webhook(self, punch_type, detailed_log=False):
        """發送 Webhook 請求"""
        try:
            data = {
                "type": punch_type,
                "timestamp": datetime.now().isoformat(),
                "message": f"自動打卡系統 - {punch_type}"
            }

            if detailed_log:
                self.logger.info(f"發送 Webhook 請求 - {punch_type}")
                self.logger.info(f"URL: {self.webhook_url}")
                self.logger.info(f"Data: {json.dumps(data, ensure_ascii=False)}")

            response = requests.post(
                self.webhook_url,
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )

            # 修改：200-299 都視為成功
            if 200 <= response.status_code < 300:
                self.logger.info(f"Webhook 請求成功 - {punch_type}, 狀態碼: {response.status_code}")
                return response
            else:
                response_text = response.text[:200] if response.text else "無回應內容"
                self.logger.warning(
                    f"Webhook 請求失敗 - {punch_type}, 狀態碼: {response.status_code}, 回應: {response_text}")
                return response

        except requests.exceptions.Timeout:
            self.logger.error(f"Webhook 請求超時 - {punch_type}")
            return None
        except requests.exceptions.ConnectionError:
            self.logger.error(f"Webhook 連線錯誤 - {punch_type}")
            return None
        except Exception as e:
            self.logger.error(f"Webhook 請求異常 - {punch_type}: {e}")
            return None

    def start_scheduler(self):
        """啟動排程器"""

        def scheduler():
            self.logger.info("排程器啟動")
            # 產生今日隨機時間
            self.generate_random_times()

            while True:
                try:
                    current_time = datetime.now()
                    current_date = current_time.date()

                    # 檢查是否需要重新產生隨機時間（新的一天）
                    if (self.punch_in_random_time and
                            self.punch_in_random_time.date() != current_date):
                        self.generate_random_times()

                    # 檢查上班打卡
                    if self.punch_in_mode == "exact":
                        # 精確時間模式
                        if (current_time.strftime('%H:%M') == self.punch_in_time and
                                not self.punch_in_executed):
                            self.logger.info(f"觸發上班打卡時間: {current_time.strftime('%H:%M')}")
                            self.auto_punch("上班打卡")
                            self.punch_in_executed = True
                    else:
                        # 隨機時間模式
                        if (self.punch_in_random_time and
                                current_time >= self.punch_in_random_time and
                                not self.punch_in_executed):
                            self.logger.info(f"觸發上班隨機打卡時間: {current_time.strftime('%H:%M:%S')}")
                            self.auto_punch("上班打卡")
                            self.punch_in_executed = True

                    # 檢查下班打卡
                    if self.punch_out_mode == "exact":
                        # 精確時間模式
                        if (current_time.strftime('%H:%M') == self.punch_out_time and
                                not self.punch_out_executed):
                            self.logger.info(f"觸發下班打卡時間: {current_time.strftime('%H:%M')}")
                            self.auto_punch("下班打卡")
                            self.punch_out_executed = True
                    else:
                        # 隨機時間模式
                        if (self.punch_out_random_time and
                                current_time >= self.punch_out_random_time and
                                not self.punch_out_executed):
                            self.logger.info(f"觸發下班隨機打卡時間: {current_time.strftime('%H:%M:%S')}")
                            self.auto_punch("下班打卡")
                            self.punch_out_executed = True
                    # 重置執行狀態（新的一天）
                    if current_time.hour == 0 and current_time.minute == 0:
                        self.punch_in_executed = False
                        self.punch_out_executed = False
                        self.logger.info("新的一天開始，重置打卡狀態")

                    time.sleep(30)  # 每30秒檢查一次（提高精確度）
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

            # 修改這裡：檢查狀態碼範圍
            if response and 200 <= response.status_code < 300:
                record = f"{current_time.strftime('%H:%M:%S')} - {punch_type}成功 (狀態碼: {response.status_code})"
                self.punch_records.append(record)
                self.logger.info(f"自動打卡成功: {punch_type}, 狀態碼: {response.status_code}")
            else:
                status_code = response.status_code if response else "無回應"
                record = f"{current_time.strftime('%H:%M:%S')} - {punch_type}失敗 (狀態碼: {status_code})"
                self.punch_records.append(record)
                self.logger.error(f"自動打卡失敗: {punch_type}, 狀態碼: {status_code}")

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
        log_window.geometry("900x600")

        # 建立文字區域
        log_text = tk.Text(log_window, wrap=tk.WORD, font=('Consolas', 9))
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
        today = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.status_text.insert(tk.END, f"目前時間: {today}\n")
        self.status_text.insert(tk.END,
                                f"Webhook URL: {self.webhook_url[:50]}{'...' if len(self.webhook_url) > 50 else ''}\n")
        self.status_text.insert(tk.END, "-" * 80 + "\n")

        # 顯示打卡設定
        self.status_text.insert(tk.END, "打卡設定:\n")

        # 上班打卡設定
        if self.punch_in_mode == "exact":
            self.status_text.insert(tk.END, f"  上班打卡: 精確時間 {self.punch_in_time}\n")
        else:
            self.status_text.insert(tk.END, f"  上班打卡: 隨機區間 {self.punch_in_start} ~ {self.punch_in_end}\n")
            if self.punch_in_random_time:
                random_time_str = self.punch_in_random_time.strftime('%H:%M:%S')
                executed_status = "已執行" if self.punch_in_executed else "待執行"
                self.status_text.insert(tk.END, f"    今日隨機時間: {random_time_str} ({executed_status})\n")

        # 下班打卡設定
        if self.punch_out_mode == "exact":
            self.status_text.insert(tk.END, f"  下班打卡: 精確時間 {self.punch_out_time}\n")
        else:
            self.status_text.insert(tk.END, f"  下班打卡: 隨機區間 {self.punch_out_start} ~ {self.punch_out_end}\n")
            if self.punch_out_random_time:
                random_time_str = self.punch_out_random_time.strftime('%H:%M:%S')
                executed_status = "已執行" if self.punch_out_executed else "待執行"
                self.status_text.insert(tk.END, f"    今日隨機時間: {random_time_str} ({executed_status})\n")

        self.status_text.insert(tk.END, "-" * 80 + "\n")

        # 顯示今日打卡記錄
        if self.punch_records:
            self.status_text.insert(tk.END, "今日打卡記錄:\n")
            for record in self.punch_records[-10:]:  # 只顯示最近10筆記錄
                self.status_text.insert(tk.END, f"  {record}\n")
        else:
            self.status_text.insert(tk.END, "今日尚未有打卡記錄\n")

        # 自動捲動到底部
        self.status_text.see(tk.END)

    def reset_punch_status(self):
        """手動重置打卡狀態"""
        self.punch_in_executed = False
        self.punch_out_executed = False
        self.punch_records.clear()
        self.logger.info("手動重置打卡狀態")
        messagebox.showinfo("成功", "打卡狀態已重置")
        self.update_status_display()

if __name__ == "__main__":
    root = tk.Tk()
    app = PunchCardApp(root)
    root.mainloop()

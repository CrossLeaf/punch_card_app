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
        self.root.geometry("800x800")

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

        # 檢查是否為休息日
        is_rest, rest_reason = self.is_rest_day(current_date)
        if is_rest:
            self.logger.info(f"今日為休息日，不執行打卡: {rest_reason}")
            return

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

                    time_diff = abs((current_time - target_time).total_seconds())
                    if time_diff <= 15:
                        should_punch_in = True
                        self.logger.info(f"觸發上班精確打卡時間: {current_time.strftime('%H:%M:%S')}")
                except ValueError as e:
                    self.logger.error(f"上班精確時間格式錯誤: {e}")

            elif self.punch_in_mode == "random":
                if self.punch_in_random_time:
                    time_diff = (current_time - self.punch_in_random_time).total_seconds()
                    if 0 <= time_diff <= 30:
                        should_punch_in = True
                        self.logger.info(
                            f"觸發上班隨機打卡時間: {current_time.strftime('%H:%M:%S')}, 目標時間: {self.punch_in_random_time.strftime('%H:%M:%S')}")

            if should_punch_in:
                self.punch_in_executed = True
                self.schedule_punch("上班打卡")

        # 檢查下班打卡
        if not self.punch_out_executed:
            should_punch_out = False

            if self.punch_out_mode == "exact":
                target_time_str = self.punch_out_time
                try:
                    target_time = datetime.strptime(f"{current_date} {target_time_str}", '%Y-%m-%d %H:%M')

                    time_diff = abs((current_time - target_time).total_seconds())
                    if time_diff <= 15:
                        should_punch_out = True
                        self.logger.info(f"觸發下班精確打卡時間: {current_time.strftime('%H:%M:%S')}")
                except ValueError as e:
                    self.logger.error(f"下班精確時間格式錯誤: {e}")

            elif self.punch_out_mode == "random":
                if self.punch_out_random_time:
                    time_diff = (current_time - self.punch_out_random_time).total_seconds()
                    if 0 <= time_diff <= 30:
                        should_punch_out = True
                        self.logger.info(
                            f"觸發下班隨機打卡時間: {current_time.strftime('%H:%M:%S')}, 目標時間: {self.punch_out_random_time.strftime('%H:%M:%S')}")

            if should_punch_out:
                self.punch_out_executed = True
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

                    # 原有設定
                    self.punch_in_time = config.get('punch_in_time', '09:00')
                    self.punch_out_time = config.get('punch_out_time', '18:00')
                    self.punch_in_start = config.get('punch_in_start', '09:00')
                    self.punch_in_end = config.get('punch_in_end', '09:20')
                    self.punch_out_start = config.get('punch_out_start', '18:00')
                    self.punch_out_end = config.get('punch_out_end', '18:20')
                    self.punch_in_mode = config.get('punch_in_mode', 'exact')
                    self.punch_out_mode = config.get('punch_out_mode', 'exact')

                    # 新增：週末設定
                    self.weekend_mode = config.get('weekend_mode', 'small')  # 'big' 或 'small'
                    self.weekend_start_date = config.get('weekend_start_date', None)  # 週末循環起始日期

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

        # 新增：週末預設設定
        self.weekend_mode = 'small'  # 預設為小周末
        self.weekend_start_date = None

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
            'punch_out_mode': self.punch_out_mode,
            # 新增：週末設定
            'weekend_mode': self.weekend_mode,
            'weekend_start_date': self.weekend_start_date
        }
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            self.logger.info("設定檔儲存成功")
        except Exception as e:
            self.logger.error(f"儲存設定失敗: {e}")
            messagebox.showerror("錯誤", f"儲存設定失敗: {e}")

    def get_current_weekend_type(self):
        """取得當前週末類型"""
        if not self.weekend_start_date:
            # 如果沒有設定起始日期，使用當前日期作為起始點
            self.weekend_start_date = datetime.now().strftime('%Y-%m-%d')
            self.save_config()

        try:
            start_date = datetime.strptime(self.weekend_start_date, '%Y-%m-%d').date()
            current_date = datetime.now().date()

            # 計算從起始日期到現在經過了多少週
            days_diff = (current_date - start_date).days
            weeks_passed = days_diff // 7

            # 根據起始週末模式和經過的週數判斷當前週末類型
            if self.weekend_mode == 'big':
                # 如果起始是大周末，奇數週為小周末，偶數週為大周末
                current_type = 'small' if weeks_passed % 2 == 1 else 'big'
            else:
                # 如果起始是小周末，奇數週為大周末，偶數週為小周末
                current_type = 'big' if weeks_passed % 2 == 1 else 'small'

            return current_type
        except Exception as e:
            self.logger.error(f"計算週末類型失敗: {e}")
            return 'small'  # 預設返回小周末

    def is_rest_day(self, date=None):
        """判斷是否為休息日"""
        if date is None:
            date = datetime.now().date()

        weekday = date.weekday()  # 0=Monday, 1=Tuesday, ..., 6=Sunday

        # 星期一永遠是休息日
        if weekday == 0:  # Monday
            return True, "星期一休息日"

        # 星期二只在大周末時是休息日
        if weekday == 1:  # Tuesday
            current_weekend_type = self.get_current_weekend_type()
            if current_weekend_type == 'big':
                return True, "大周末星期二休息日"

        # 其他日子不是休息日
        return False, ""

    def get_weekend_status_text(self):
        """取得週末狀態文字"""
        current_type = self.get_current_weekend_type()
        if current_type == 'big':
            return "目前為大週末週期（週一、二休息）"
        else:
            return "目前為小週末週期（週一休息）"

    def generate_random_times(self):
        """產生隨機打卡時間"""
        current_date = datetime.now().date()

        try:
            # 上班隨機時間
            start_time = datetime.strptime(f"{current_date} {self.punch_in_start}", '%Y-%m-%d %H:%M')
            end_time = datetime.strptime(f"{current_date} {self.punch_in_end}", '%Y-%m-%d %H:%M')

            time_diff = int((end_time - start_time).total_seconds())
            random_seconds = random.randint(0, time_diff)
            self.punch_in_random_time = start_time + timedelta(seconds=random_seconds)

            # 下班隨機時間
            start_time = datetime.strptime(f"{current_date} {self.punch_out_start}", '%Y-%m-%d %H:%M')
            end_time = datetime.strptime(f"{current_date} {self.punch_out_end}", '%Y-%m-%d %H:%M')

            time_diff = int((end_time - start_time).total_seconds())
            random_seconds = random.randint(0, time_diff)
            self.punch_out_random_time = start_time + timedelta(seconds=random_seconds)

            self.logger.info(
                f"產生隨機時間 - 上班: {self.punch_in_random_time.strftime('%H:%M:%S')}, 下班: {self.punch_out_random_time.strftime('%H:%M:%S')}")

        except Exception as e:
            self.logger.error(f"產生隨機時間失敗: {e}")

    def send_webhook(self, message):
        """發送 Webhook"""
        try:
            if not self.webhook_url:
                raise Exception("Webhook URL 未設定")

            payload = {"text": message}
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            return response
        except Exception as e:
            self.logger.error(f"發送 Webhook 失敗: {e}")
            return None

    def setup_ui(self):
        """設置使用者介面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 配置網格權重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

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
        ttk.Label(punch_in_frame, text="精確時間:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.punch_in_time_var = tk.StringVar(value=self.punch_in_time)
        ttk.Entry(punch_in_frame, textvariable=self.punch_in_time_var, width=10).grid(row=1, column=1, sticky=tk.W,
                                                                                      pady=5)

        # 隨機區間設定
        ttk.Label(punch_in_frame, text="隨機區間:").grid(row=2, column=0, sticky=tk.W, pady=5)
        time_frame1 = ttk.Frame(punch_in_frame)
        time_frame1.grid(row=2, column=1, columnspan=3, sticky=tk.W, pady=5)

        self.punch_in_start_var = tk.StringVar(value=self.punch_in_start)
        self.punch_in_end_var = tk.StringVar(value=self.punch_in_end)
        ttk.Entry(time_frame1, textvariable=self.punch_in_start_var, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Label(time_frame1, text="到").pack(side=tk.LEFT, padx=5)
        ttk.Entry(time_frame1, textvariable=self.punch_in_end_var, width=8).pack(side=tk.LEFT, padx=2)

        # 下班打卡設定
        punch_out_frame = ttk.LabelFrame(main_frame, text="下班打卡設定", padding="10")
        punch_out_frame.grid(row=2, column=0, columnspan=5, sticky=(tk.W, tk.E), pady=10)

        self.punch_out_mode_var = tk.StringVar(value=self.punch_out_mode)
        ttk.Radiobutton(punch_out_frame, text="精確時間", variable=self.punch_out_mode_var,
                        value="exact", command=self.update_punch_out_mode).grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Radiobutton(punch_out_frame, text="隨機區間", variable=self.punch_out_mode_var,
                        value="random", command=self.update_punch_out_mode).grid(row=0, column=1, sticky=tk.W, padx=5)

        # 精確時間設定
        ttk.Label(punch_out_frame, text="精確時間:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.punch_out_time_var = tk.StringVar(value=self.punch_out_time)
        ttk.Entry(punch_out_frame, textvariable=self.punch_out_time_var, width=10).grid(row=1, column=1, sticky=tk.W,
                                                                                        pady=5)

        # 隨機區間設定
        ttk.Label(punch_out_frame, text="隨機區間:").grid(row=2, column=0, sticky=tk.W, pady=5)
        time_frame2 = ttk.Frame(punch_out_frame)
        time_frame2.grid(row=2, column=1, columnspan=3, sticky=tk.W, pady=5)

        self.punch_out_start_var = tk.StringVar(value=self.punch_out_start)
        self.punch_out_end_var = tk.StringVar(value=self.punch_out_end)
        ttk.Entry(time_frame2, textvariable=self.punch_out_start_var, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Label(time_frame2, text="到").pack(side=tk.LEFT, padx=5)
        ttk.Entry(time_frame2, textvariable=self.punch_out_end_var, width=8).pack(side=tk.LEFT, padx=2)

        # 週末設定區域
        weekend_frame = ttk.LabelFrame(main_frame, text="週末設定", padding="10")
        weekend_frame.grid(row=3, column=0, columnspan=5, sticky=(tk.W, tk.E), pady=10)

        # 週末狀態顯示
        self.weekend_status_var = tk.StringVar()
        self.weekend_status_label = ttk.Label(weekend_frame, textvariable=self.weekend_status_var,
                                              font=('Arial', 10, 'bold'))
        self.weekend_status_label.grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=5)

        # 週末設定按鈕
        button_frame = ttk.Frame(weekend_frame)
        button_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        ttk.Button(button_frame, text="設為大週末週期起點",
                   command=self.set_big_weekend_start).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="重置週末設置",
                   command=self.reset_weekend_settings).pack(side=tk.LEFT, padx=5)

        # 注意事項
        notes_frame = ttk.LabelFrame(weekend_frame, text="注意事項", padding="5")
        notes_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)

        notes = [
            "• 星期一永遠是休息日，不會發送提醒",
            "• 大周末時，星期一和星期二都是休息日",
            "• 小周末時，只有星期一是休息日",
            "• 大小周末交替進行"
        ]

        for i, note in enumerate(notes):
            ttk.Label(notes_frame, text=note, font=('Arial', 9)).grid(row=i, column=0, sticky=tk.W, pady=2)

        # 控制按鈕
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=4, column=0, columnspan=5, pady=20)

        ttk.Button(control_frame, text="儲存設定", command=self.save_settings).pack(side=tk.LEFT, padx=10)
        ttk.Button(control_frame, text="手動上班打卡", command=lambda: self.manual_punch("上班打卡")).pack(side=tk.LEFT,
                                                                                                           padx=10)
        ttk.Button(control_frame, text="手動下班打卡", command=lambda: self.manual_punch("下班打卡")).pack(side=tk.LEFT,
                                                                                                           padx=10)

        self.auto_punch_var = tk.BooleanVar(value=self.auto_punch_enabled)
        ttk.Checkbutton(control_frame, text="啟用自動打卡", variable=self.auto_punch_var,
                        command=self.toggle_auto_punch).pack(side=tk.LEFT, padx=10)

        # 狀態顯示
        status_frame = ttk.LabelFrame(main_frame, text="系統狀態", padding="10")
        status_frame.grid(row=5, column=0, columnspan=5, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)

        self.status_var = tk.StringVar()
        status_label = ttk.Label(status_frame, textvariable=self.status_var, font=('Courier', 10))
        status_label.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # 打卡記錄
        records_frame = ttk.LabelFrame(main_frame, text="打卡記錄", padding="10")
        records_frame.grid(row=6, column=0, columnspan=5, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)

        # 配置網格權重
        main_frame.rowconfigure(5, weight=1)
        main_frame.rowconfigure(6, weight=1)
        status_frame.rowconfigure(0, weight=1)
        records_frame.rowconfigure(0, weight=1)

        self.records_text = tk.Text(records_frame, height=8, width=80)
        scrollbar = ttk.Scrollbar(records_frame, orient="vertical", command=self.records_text.yview)
        self.records_text.configure(yscrollcommand=scrollbar.set)

        self.records_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        records_frame.columnconfigure(0, weight=1)

        # 初始化狀態顯示
        self.update_weekend_status()
        self.update_status_display()

        # 定期更新狀態顯示
        self.update_display_timer()

    def update_punch_in_mode(self):
        """更新上班打卡模式"""
        self.punch_in_mode = self.punch_in_mode_var.get()

    def update_punch_out_mode(self):
        """更新下班打卡模式"""
        self.punch_out_mode = self.punch_out_mode_var.get()

    def set_big_weekend_start(self):
        """設定大週末起始點"""
        self.weekend_mode = 'big'
        self.weekend_start_date = datetime.now().strftime('%Y-%m-%d')
        self.save_config()
        self.update_weekend_status()
        self.logger.info(f"設定大週末起始點: {self.weekend_start_date}")
        messagebox.showinfo("成功", "已設定為大週末週期起點")

    def reset_weekend_settings(self):
        """重置週末設置"""
        self.weekend_mode = 'small'
        self.weekend_start_date = datetime.now().strftime('%Y-%m-%d')
        self.save_config()
        self.update_weekend_status()
        self.logger.info("重置週末設置為小週末")
        messagebox.showinfo("成功", "週末設置已重置")

    def update_weekend_status(self):
        """更新週末狀態顯示"""
        status_text = self.get_weekend_status_text()
        self.weekend_status_var.set(status_text)

    def save_settings(self):
        """儲存所有設定"""
        try:
            # 更新設定值
            self.webhook_url = self.url_var.get()
            self.punch_in_time = self.punch_in_time_var.get()
            self.punch_out_time = self.punch_out_time_var.get()
            self.punch_in_start = self.punch_in_start_var.get()
            self.punch_in_end = self.punch_in_end_var.get()
            self.punch_out_start = self.punch_out_start_var.get()
            self.punch_out_end = self.punch_out_end_var.get()
            self.punch_in_mode = self.punch_in_mode_var.get()
            self.punch_out_mode = self.punch_out_mode_var.get()

            # 驗證時間格式
            self.validate_time_format()

            # 儲存設定
            self.save_config()

            # 重新產生隨機時間
            self.generate_random_times()

            messagebox.showinfo("成功", "設定已儲存")
            self.logger.info("使用者設定已儲存")

        except Exception as e:
            error_msg = f"儲存設定時發生錯誤: {e}"
            messagebox.showerror("錯誤", error_msg)
            self.logger.error(error_msg)

    def validate_time_format(self):
        """驗證時間格式"""
        time_fields = [
            (self.punch_in_time, "上班精確時間"),
            (self.punch_out_time, "下班精確時間"),
            (self.punch_in_start, "上班隨機開始時間"),
            (self.punch_in_end, "上班隨機結束時間"),
            (self.punch_out_start, "下班隨機開始時間"),
            (self.punch_out_end, "下班隨機結束時間")
        ]

        for time_str, field_name in time_fields:
            try:
                datetime.strptime(time_str, '%H:%M')
            except ValueError:
                raise ValueError(f"{field_name} 格式錯誤，請使用 HH:MM 格式")

    def manual_punch(self, punch_type):
        """手動打卡"""

        def punch_task():
            try:
                current_time = datetime.now()
                self.logger.info(f"開始執行手動打卡: {punch_type}")

                response = self.send_webhook(punch_type)

                if response and 200 <= response.status_code < 300:
                    record = f"{current_time.strftime('%H:%M:%S')} - {punch_type}成功 (手動, 狀態碼: {response.status_code})"
                    self.punch_records.append(record)
                    self.logger.info(f"手動打卡成功: {punch_type}")
                    self.root.after(0, lambda: messagebox.showinfo("成功", f"{punch_type}成功"))
                else:
                    status_code = response.status_code if response else "無回應"
                    record = f"{current_time.strftime('%H:%M:%S')} - {punch_type}失敗 (手動, 狀態碼: {status_code})"
                    self.punch_records.append(record)
                    self.logger.error(f"手動打卡失敗: {punch_type}")
                    self.root.after(0, lambda: messagebox.showerror("失敗", f"{punch_type}失敗"))

                self.root.after(0, self.update_status_display)

            except Exception as e:
                current_time = datetime.now()
                record = f"{current_time.strftime('%H:%M:%S')} - {punch_type}錯誤 (手動): {e}"
                self.punch_records.append(record)
                self.logger.error(f"手動打卡時發生異常: {e}")
                self.root.after(0, lambda: messagebox.showerror("錯誤", f"打卡時發生錯誤: {e}"))
                self.root.after(0, self.update_status_display)

        threading.Thread(target=punch_task, daemon=True).start()

    def toggle_auto_punch(self):
        """切換自動打卡狀態"""
        self.auto_punch_enabled = self.auto_punch_var.get()
        status = "啟用" if self.auto_punch_enabled else "停用"
        self.logger.info(f"自動打卡已{status}")
        messagebox.showinfo("狀態更新", f"自動打卡已{status}")

    def update_status_display(self):
        """更新狀態顯示"""
        current_time = datetime.now()

        # 檢查是否為休息日
        is_rest, rest_reason = self.is_rest_day()

        if is_rest:
            status_text = f"目前時間: {current_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            status_text += f"狀態: 休息日 ({rest_reason})\n"
            status_text += "自動打卡: 暫停\n"
        else:
            status_text = f"目前時間: {current_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            status_text += f"自動打卡: {'啟用' if self.auto_punch_enabled else '停用'}\n"

            # 顯示今日打卡狀態
            if self.punch_in_executed:
                status_text += "上班打卡: 已完成\n"
            else:
                if self.punch_in_mode == "exact":
                    status_text += f"上班打卡: 等待 ({self.punch_in_time})\n"
                else:
                    if self.punch_in_random_time:
                        status_text += f"上班打卡: 等待 ({self.punch_in_random_time.strftime('%H:%M:%S')})\n"
                    else:
                        status_text += "上班打卡: 等待\n"

            if self.punch_out_executed:
                status_text += "下班打卡: 已完成\n"
            else:
                if self.punch_out_mode == "exact":
                    status_text += f"下班打卡: 等待 ({self.punch_out_time})\n"
                else:
                    if self.punch_out_random_time:
                        status_text += f"下班打卡: 等待 ({self.punch_out_random_time.strftime('%H:%M:%S')})\n"
                    else:
                        status_text += "下班打卡: 等待\n"

        self.status_var.set(status_text)

        # 更新打卡記錄
        if hasattr(self, 'records_text'):
            records_display = "\n".join(self.punch_records[-10:])  # 只顯示最近10筆記錄
            self.records_text.delete(1.0, tk.END)
            self.records_text.insert(1.0, records_display)
            # 自動滾動到最底部
            self.records_text.see(tk.END)

    def update_display_timer(self):
        """定期更新顯示"""
        self.update_status_display()
        # 每秒更新一次顯示
        self.root.after(1000, self.update_display_timer)

    def on_closing(self):
        """程式關閉時的處理"""
        self.scheduler_running = False
        self.logger.info("應用程式正在關閉")
        self.root.destroy()


def main():
    """主程式入口"""
    root = tk.Tk()
    app = PunchCardApp(root)

    # 設定關閉事件處理
    root.protocol("WM_DELETE_WINDOW", app.on_closing)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("程式被使用者中斷")
    except Exception as e:
        print(f"程式執行時發生錯誤: {e}")
        logging.error(f"程式執行時發生錯誤: {e}")


if __name__ == "__main__":
    main()


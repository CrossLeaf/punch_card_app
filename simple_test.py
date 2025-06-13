# simple_test.py - 極簡版測試腳本
from datetime import datetime, date, timedelta
import json
import os

# 直接將結果寫入文件
output_file = open('weekend_test_result.txt', 'w', encoding='utf-8')

def write_log(message):
    """寫入日誌到文件"""
    output_file.write(message + '\n')
    
# 載入設定檔
config_file = "punch_config.json"
weekend_mode = "small"  # 預設為小周末
weekend_start_date = None

try:
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
            weekend_mode = config.get('weekend_mode', 'small')
            weekend_start_date = config.get('weekend_start_date', None)
            
        write_log(f"✅ 設定檔載入成功")
    else:
        write_log(f"⚠️ 設定檔不存在，使用預設設定")
        weekend_start_date = datetime.now().strftime('%Y-%m-%d')
except Exception as e:
    write_log(f"❌ 載入設定檔失敗: {e}")
    weekend_start_date = datetime.now().strftime('%Y-%m-%d')

write_log(f"📅 週末起始日期: {weekend_start_date}")
write_log(f"🔄 起始週末模式: {weekend_mode}\n")

# 測試函數
def test_weekend_type(test_date_str):
    """測試指定日期的週末類型"""
    # 將日期字符串轉換為日期對象
    test_date = datetime.strptime(test_date_str, '%Y-%m-%d').date()
    start_date = datetime.strptime(weekend_start_date, '%Y-%m-%d').date()
    
    # 計算週數差
    days_diff = (test_date - start_date).days
    weeks_diff = days_diff // 7
    
    write_log(f"測試日期: {test_date_str}")
    write_log(f"起始日期: {weekend_start_date}")
    write_log(f"起始模式: {weekend_mode}")
    write_log(f"相差天數: {days_diff}")
    write_log(f"相差週數: {weeks_diff}")
    
    # 根據週數差決定週末類型
    if weeks_diff % 2 == 0:
        current_type = weekend_mode
    else:
        current_type = "big" if weekend_mode == "small" else "small"
    
    weekday = test_date.weekday()
    weekday_names = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
    
    # 判斷是否為休息日
    is_rest = False
    rest_reason = "正常工作日"
    
    # 星期一永遠是休息日
    if weekday == 0:  # Monday
        is_rest = True
        rest_reason = "星期一休息日"
    
    # 星期二只在大周末時是休息日
    if weekday == 1:  # Tuesday
        if current_type == 'big':
            is_rest = True
            rest_reason = "大周末星期二休息日"
    
    write_log(f"日期: {test_date_str} ({weekday_names[weekday]})")
    write_log(f"週末類型: {current_type}")
    write_log(f"是否休息: {'是' if is_rest else '否'} ({rest_reason})")
    write_log("-" * 50)
    
    return {
        "date": test_date_str,
        "weekday": weekday_names[weekday],
        "weekend_type": current_type,
        "is_rest": is_rest,
        "rest_reason": rest_reason
    }

# 新增：測試日期範圍函數
def test_date_range(start_date_str, end_date_str):
    """測試指定日期範圍內的週末類型"""
    write_log(f"===== 測試日期範圍: {start_date_str} 至 {end_date_str} =====\n")
    
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    
    # 統計數據
    total_days = (end_date - start_date).days + 1
    rest_days = 0
    work_days = 0
    big_weekend_days = 0
    small_weekend_days = 0
    
    # 生成日期範圍
    current_date = start_date
    results = []
    
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        result = test_weekend_type(date_str)
        results.append(result)
        
        # 更新統計數據
        if result["is_rest"]:
            rest_days += 1
        else:
            work_days += 1
            
        if result["weekend_type"] == "big":
            big_weekend_days += 1
        else:
            small_weekend_days += 1
        
        # 移至下一天
        current_date += timedelta(days=1)
    
    # 輸出統計結果
    write_log("\n===== 統計結果 =====")
    write_log(f"總天數: {total_days}")
    write_log(f"工作日: {work_days} ({work_days/total_days*100:.1f}%)")
    write_log(f"休息日: {rest_days} ({rest_days/total_days*100:.1f}%)")
    write_log(f"大周末天數: {big_weekend_days} ({big_weekend_days/total_days*100:.1f}%)")
    write_log(f"小周末天數: {small_weekend_days} ({small_weekend_days/total_days*100:.1f}%)")
    write_log("-" * 50)
    
    return results

# 預設測試日期列表
default_test_dates = [
    date.today().strftime('%Y-%m-%d'),  # 今天
    '2025-06-09',  # 參考日期
    '2025-06-10',  # 週末起始日期
    '2025-06-11',  # 起始日期+1天
    '2025-06-16',  # 起始日期+6天
    '2025-06-17',  # 起始日期+7天
    '2025-06-24',  # 起始日期+14天
    '2025-07-01',  # 起始日期+21天
    '2025-07-08',  # 起始日期+28天
]

# 主程序
write_log("===== 大小周邏輯測試結果 =====\n")

# 使用者輸入日期範圍
try:
    print("請選擇測試模式:")
    print("1. 測試預設日期列表")
    print("2. 測試指定日期範圍")
    choice = input("請輸入選項 (1 或 2): ")
    
    if choice == "1":
        # 測試預設日期列表
        for test_date in default_test_dates:
            test_weekend_type(test_date)
    elif choice == "2":
        # 測試日期範圍
        start_date = input("請輸入開始日期 (YYYY-MM-DD): ")
        end_date = input("請輸入結束日期 (YYYY-MM-DD): ")
        test_date_range(start_date, end_date)
    else:
        print("無效選項，使用預設日期列表測試")
        for test_date in default_test_dates:
            test_weekend_type(test_date)
            
except Exception as e:
    write_log(f"❌ 測試過程中發生錯誤: {e}")
    print(f"測試過程中發生錯誤: {e}")
    # 發生錯誤時使用預設日期列表
    for test_date in default_test_dates:
        test_weekend_type(test_date)

output_file.close()

print("測試已完成，請查看 weekend_test_result.txt 文件獲取結果。")
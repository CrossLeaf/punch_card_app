# setup_task_scheduler.py
import os
import sys
import subprocess
import json
from pathlib import Path
from datetime import datetime


class TaskSchedulerSetup:
    def __init__(self):
        self.task_name = "AutoPunchCard"
        self.current_dir = Path(__file__).parent.absolute()
        self.python_exe = sys.executable
        self.script_path = self.current_dir / "punch_card_app.py"

    def create_task_xml(self):
        """建立工作排程器 XML 設定檔"""

        # 取得當前使用者名稱
        username = os.getenv('USERNAME')

        xml_content = f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Date>{datetime.now().isoformat()}</Date>
    <Author>{username}</Author>
    <Description>自動打卡系統 - 開機時自動啟動</Description>
    <URI>\\{self.task_name}</URI>
  </RegistrationInfo>

  <!-- 觸發條件：使用者登入時執行 -->
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>{username}</UserId>
      <Delay>PT30S</Delay>  <!-- 延遲30秒啟動，避免系統負載過重 -->
    </LogonTrigger>
  </Triggers>

  <!-- 執行主體設定 -->
  <Principals>
    <Principal id="Author">
      <UserId>{username}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>

  <!-- 任務設定 -->
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>  <!-- 避免重複執行 -->
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>  <!-- 電池模式也執行 -->
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>  <!-- 系統可用時立即執行 -->
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>  <!-- 需要網路連線 -->
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>  <!-- 允許手動執行 -->
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>  <!-- 不隱藏任務 -->
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <DisallowStartOnRemoteAppSession>false</DisallowStartOnRemoteAppSession>
    <UseUnifiedSchedulingEngine>true</UseUnifiedSchedulingEngine>
    <WakeToRun>false</WakeToRun>  <!-- 不喚醒電腦 -->
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>  <!-- 無執行時間限制 -->
    <Priority>7</Priority>  <!-- 正常優先級 -->
    <RestartOnFailure>
      <Interval>PT1M</Interval>  <!-- 失敗後1分鐘重試 -->
      <Count>3</Count>  <!-- 最多重試3次 -->
    </RestartOnFailure>
  </Settings>

  <!-- 執行動作 -->
  <Actions Context="Author">
    <Exec>
      <Command>"{self.python_exe}"</Command>
      <Arguments>"{self.script_path}"</Arguments>
      <WorkingDirectory>{self.current_dir}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>'''

        return xml_content

    def create_task(self):
        """建立工作排程器任務"""
        print("🔧 開始建立工作排程器任務...")
        print("-" * 50)

        # 檢查必要檔案
        if not self.script_path.exists():
            print(f"❌ 找不到主程式檔案: {self.script_path}")
            return False

        # 建立暫存 XML 檔案
        xml_content = self.create_task_xml()
        xml_file = self.current_dir / f"{self.task_name}_temp.xml"

        try:
            # 寫入 XML 檔案
            with open(xml_file, 'w', encoding='utf-16') as f:
                f.write(xml_content)

            print(f"📄 XML 設定檔已建立: {xml_file}")

            # 刪除現有任務（如果存在）
            print("🗑️  檢查並刪除現有任務...")
            delete_cmd = f'schtasks /delete /tn "{self.task_name}" /f'
            subprocess.run(delete_cmd, shell=True, capture_output=True)

            # 建立新任務
            print("✨ 建立新的排程任務...")
            create_cmd = f'schtasks /create /tn "{self.task_name}" /xml "{xml_file}"'
            result = subprocess.run(create_cmd, shell=True, capture_output=True, text=True)

            if result.returncode == 0:
                print("✅ 工作排程器任務建立成功！")
                print(f"   任務名稱: {self.task_name}")
                print(f"   觸發條件: 使用者登入時")
                print(f"   延遲時間: 30秒")
                print(f"   執行程式: {self.script_path}")

                # 顯示任務資訊
                self.show_task_info()
                return True
            else:
                print(f"❌ 建立任務失敗:")
                print(f"   錯誤訊息: {result.stderr}")
                return False

        except Exception as e:
            print(f"❌ 建立任務時發生錯誤: {e}")
            return False

        finally:
            # 清理暫存檔案
            if xml_file.exists():
                try:
                    xml_file.unlink()
                    print("🧹 暫存檔案已清理")
                except:
                    pass

    def show_task_info(self):
        """顯示任務詳細資訊"""
        print("\n📊 任務詳細資訊:")
        print("-" * 30)

        try:
            cmd = f'schtasks /query /tn "{self.task_name}" /fo LIST /v'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='cp950')

            if result.returncode == 0:
                lines = result.stdout.split('\n')
                important_fields = [
                    '工作名稱:', 'TaskName:',
                    '狀態:', 'Status:',
                    '下次執行時間:', 'Next Run Time:',
                    '上次執行時間:', 'Last Run Time:',
                    '上次結果:', 'Last Result:'
                ]

                for line in lines:
                    for field in important_fields:
                        if field in line:
                            print(f"   {line.strip()}")
                            break

        except Exception as e:
            print(f"   無法取得詳細資訊: {e}")

    def delete_task(self):
        """刪除工作排程器任務"""
        print("🗑️  刪除工作排程器任務...")
        print("-" * 50)

        try:
            cmd = f'schtasks /delete /tn "{self.task_name}" /f'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

            if result.returncode == 0:
                print("✅ 任務刪除成功！")
                return True
            else:
                print(f"❌ 刪除任務失敗: {result.stderr}")
                return False

        except Exception as e:
            print(f"❌ 刪除任務時發生錯誤: {e}")
            return False

    def test_task(self):
        """測試任務執行"""
        print("🧪 測試任務執行...")
        print("-" * 50)

        try:
            cmd = f'schtasks /run /tn "{self.task_name}"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

            if result.returncode == 0:
                print("✅ 任務測試執行成功！")
                print("   請檢查程式是否正常啟動")
                return True
            else:
                print(f"❌ 任務測試失敗: {result.stderr}")
                return False

        except Exception as e:
            print(f"❌ 測試任務時發生錯誤: {e}")
            return False

    def check_task_status(self):
        """檢查任務狀態"""
        print("🔍 檢查任務狀態...")
        print("-" * 50)

        try:
            cmd = f'schtasks /query /tn "{self.task_name}"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='cp950')

            if result.returncode == 0:
                print("✅ 任務存在且正常")
                print(result.stdout)
                return True
            else:
                print("❌ 任務不存在或有問題")
                return False

        except Exception as e:
            print(f"❌ 檢查任務時發生錯誤: {e}")
            return False


def main():
    """主程式"""
    print("=" * 60)
    print("🔧 Windows 工作排程器設定工具")
    print("=" * 60)

    setup = TaskSchedulerSetup()

    while True:
        print("\n請選擇操作:")
        print("1. 建立自動啟動任務")
        print("2. 刪除自動啟動任務")
        print("3. 檢查任務狀態")
        print("4. 測試任務執行")
        print("5. 退出程式")

        choice = input("\n請輸入選項 (1-5): ").strip()

        if choice == "1":
            setup.create_task()

        elif choice == "2":
            setup.delete_task()

        elif choice == "3":
            setup.check_task_status()

        elif choice == "4":
            setup.test_task()

        elif choice == "5":
            print("👋 退出程式")
            break

        else:
            print("❌ 無效的選項，請重新選擇")

        input("\n按 Enter 鍵繼續...")


if __name__ == "__main__":
    main()

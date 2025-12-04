import json
import os
from typing import Dict
import config

class MockDBManager:
    """
    负责构建 Java 系统运行所需的外部数据环境 (JSON Files + Interface Files)
    """
    def __init__(self):
        self.data_dir = config.DATA_DIR
        # 确保基础目录存在
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    def inject_test_data(self, setup_state: Dict):
        """
        将测试前置状态写入 JSON 文件，供 Java 系统读取
        """
        # 写入账户表
        acc_path = os.path.join(self.data_dir, "Accounts.json")
        with open(acc_path, 'w', encoding='utf-8') as f:
            json.dump(setup_state.get('accounts', []), f, indent=2)
            
        # 写入持仓表
        hold_path = os.path.join(self.data_dir, "Holdings.json")
        with open(hold_path, 'w', encoding='utf-8') as f:
            json.dump(setup_state.get('holdings', []), f, indent=2)
            
        # print(f"   💾 [DB] State injected.")

    def create_input_file(self, content: str, relative_path: str) -> str:
        """
        Tool Function: 根据 Agent 指定的路径写入文件内容
        :param content: 文件内容
        :param relative_path: 相对路径，例如 "input/20231027/REQ_001.txt"
        :return: 文件的绝对路径
        """
        # 防止路径遍历攻击，确保路径在 data_dir 下
        full_path = os.path.join(self.data_dir, relative_path)
        
        # 自动创建父目录 (mkdir -p)
        parent_dir = os.path.dirname(full_path)
        if not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
            
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        return full_path
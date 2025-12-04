import subprocess
import os
import config

class JavaSUTConnector:
    """
    负责调用外部 Java 进程
    """
    def process_file(self, input_file_path: str) -> str:
        """
        调用 Java 程序处理文件。
        假设 Java 程序用法: java -jar app.jar <input_path>
        并且 Java 程序会将结果输出到 config.OUTPUT_DIR 下的固定文件或 stdout
        """
        print(f"   ☕ [Java SUT] calling Java process...")
        
        # 1. 构造命令
        # 这里的命令取决于你的 Java main 方法如何接收参数
        cmd = config.JAVA_EXECUTABLE_CMD + [input_file_path]
        
        try:
            # 2. 执行命令
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False # 不抛出异常，手动处理
            )
            
            if result.returncode != 0:
                print(f"   ❌ Java Execution Error: {result.stderr}")
                return None
                
            print(f"   ✅ Java Execution Success. Stdout: {result.stdout.strip()[:50]}...")
            
            # 3. 确定输出文件位置
            # 假设 Java 程序约定输出到 output/confirm.txt
            # 或者你可以解析 stdout 获取输出路径
            expected_output = os.path.join(config.OUTPUT_DIR, "confirm.txt")
            
            if os.path.exists(expected_output):
                return expected_output
            else:
                print(f"   ⚠️ Output file not found at {expected_output}")
                return None
                
        except FileNotFoundError:
            print("   ❌ Error: Java executable not found. Please check JAVA_EXECUTABLE_CMD in config.py")
            return None
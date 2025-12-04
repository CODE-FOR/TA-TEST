import os

# --- 全局配置 ---

# Java 源码路径
JAVA_SOURCE_ROOT = "../src"
# 文档路径 (新增)
DOC_SOURCE_ROOT = "../doc"

# Java 执行命令
JAVA_EXECUTABLE_CMD = ["bash", "run.sh"]

# 路径配置
VECTOR_DB_PATH = "./chroma_db_unified"
DATA_DIR = "./test_data"
INPUT_DIR = os.path.join(DATA_DIR, "input")
OUTPUT_DIR = os.path.join(DATA_DIR, "output")
RULES_DIR = os.path.join(DATA_DIR, "rules_draft") # 存放待审核规则的目录

# 模型配置
OPENAI_MODEL = "gemini-3-pro-preview"
EMBEDDING_MODEL = "text-embedding-3-large"
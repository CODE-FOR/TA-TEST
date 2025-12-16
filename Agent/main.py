import argparse
import os
import json
import json5
import time
import shutil
import logging
import re
from typing import List

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from dotenv import load_dotenv

import config
import specs
from infrastructure import MockDBManager
from rag_service import UnifiedRAGService
from agents import BusinessRuleAnalystAgent, TestCaseGeneratorAgent, TestStrategyPlannerAgent

load_dotenv()
logger = logging.getLogger("TA_Agent_Orchestrator")

# ==========================================
# Global Constants & Configuration
# ==========================================

# 建立 Key 到中文描述的映射，用于提示词增强
# 这样可以保持 specs.py 的纯净，同时给 Agent 提供语义信息
FILE_KEY_DESC_MAP = {
    "DIST_ACC": "销售商账户申请文件",
    "DIST_TRADE": "销售商交易申请文件",
    "MGR_NAV": "管理人净值文件",
    "MGR_CONFIRM": "管理人确认回执文件"
}

# 动态生成 SUPPORTED_FILE_TYPES，确保与 specs.py 严格同步
# 格式示例: ["DIST_TRADE - 销售商交易申请文件", ...]
SUPPORTED_FILE_TYPES = [
    f"{key} - {FILE_KEY_DESC_MAP.get(key, '未定义描述文件')}"
    for key in specs.FILE_SPECS.keys()
]

# ==========================================
# Main Orchestrator
# ==========================================
class Orchestrator:
    def __init__(self):
        self.db_manager = MockDBManager()
        # RAG 服务仅用于初始化数据入库，具体的查询由 Analyst Agent 的 Tool 接管
        self.rag_service = UnifiedRAGService() 
        
        # 初始化 Agents (全部来自 agents.py)
        self.planner = TestStrategyPlannerAgent(config.OPENAI_MODEL)
        self.analyst = BusinessRuleAnalystAgent()
        self.generator = TestCaseGeneratorAgent(config.OPENAI_MODEL)

    def initialize(self, reindex: bool = False):
        logger.info("Initializing Orchestrator...")
        if reindex:
            logger.info("Triggering Knowledge Base Ingestion...")
            self.rag_service.ingest_knowledge_base()
        
        # 确保目录存在
        os.makedirs(config.RULES_DIR, exist_ok=True)
        os.makedirs(config.DATA_DIR, exist_ok=True)
        logger.info("Initialization complete.")

    def phase_0_plan(self):
        """阶段零：自动规划测试主题"""
        logger.info("🚀 === PHASE 0: STRATEGY PLANNING ===")
        
        # 直接使用全局变量，无需内部 import
        file_types_str = ", ".join([t.split(' - ')[0] for t in SUPPORTED_FILE_TYPES])
        
        topics = self.planner.plan(
            system_context=specs.SYSTEM_CONTEXT,
            file_interfaces=file_types_str
        )
        
        for i, t in enumerate(topics):
            logger.info(f"   {i+1}. {t}")
        return topics

    def phase_1_analyze(self, topics):
        """阶段一：分析文档和代码，提取规则 (使用 Tool Calling Agent)"""
        logger.info("🚀 === PHASE 1: AGENTIC ANALYSIS ===")
        
        for topic in topics:
            logger.info(f"🤖 Agent Analyzing Topic: {topic}")
            
            # Agent 会自主调用 Tools (查文档、查代码、查规范)
            # 最终返回自然语言或 JSON 字符串
            result_text = str(self.analyst.analyze(topic))
            
            # 尝试从 Agent 的回复中提取 JSON 部分进行清洗和保存
            try:
                cleaned_rules = self._extract_json_from_text(result_text)
            except Exception as e:
                logger.error(f"Error extracting JSON from Agent output: {e}")
                cleaned_rules = None
            
            if cleaned_rules:
                # 文件名安全处理
                safe_topic = "".join([c if c.isalnum() else '_' for c in topic])
                filename = f"rules_{int(time.time())}_{safe_topic[:50]}.json"
                filepath = os.path.join(config.RULES_DIR, filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(cleaned_rules, f, indent=2, ensure_ascii=False)
                logger.info(f"✅ Rules saved to: {filepath}")
            else:
                logger.warning(f"⚠️ Could not parse JSON from Agent output for topic: {topic}")
                # 同时也保存原始文本以便 debug
                debug_path = os.path.join(config.RULES_DIR, f"debug_{int(time.time())}.txt")
                with open(debug_path, "w", encoding='utf-8') as f:
                    f.write(result_text)

    def phase_2_execute(self):
        """阶段二：结构化生成与归档 (使用 Structured Output Agent)"""
        logger.info("🚀 === PHASE 2: STRUCTURED GENERATION ===")
        
        try:
            rule_files = [f for f in os.listdir(config.RULES_DIR) if f.endswith(".json")]
        except FileNotFoundError:
            logger.error(f"Rules directory not found.")
            return

        if not rule_files:
            logger.error(f"No rule files found. Run Phase 1 first.")
            return

        # 创建批次目录
        batch_id = f"batch_{int(time.time())}"
        batch_dir = os.path.join(config.DATA_DIR, "generated_batches", batch_id)
        os.makedirs(batch_dir, exist_ok=True)
        logger.info(f"📂 Batch Directory: {batch_dir}")

        for r_file in rule_files:
            r_path = os.path.join(config.RULES_DIR, r_file)
            logger.info(f"📂 Processing Rules: {r_file}")
            
            try:
                with open(r_path, 'r', encoding='utf-8') as f:
                    rules = json5.load(f)
            except json5.JSONDecodeError:
                logger.error(f"Invalid JSON in {r_file}, skipping.")
                continue

            # 如果规则文件是 List，则遍历；如果是 Dict，则封装
            if isinstance(rules, dict): rules = [rules]
            
            for rule in rules:
                rule_desc = rule.get('logic', str(rule)[:50])
                logger.info(f"⚡ Generating Cases for: {rule_desc}...")
                
                # 1. 确定输入文件 (这里为了简化，使用简单的启发式或再次调用 LLM，
                # 但为了性能，我们可以在 Generator Agent 内部处理，或者由 Analyst 在 Phase 1 已经确定)
                # 此处我们将所有相关 Context 喂给 Generator
                
                # 确定相关的文件规范
                # 简单策略：把所有 Input 和 Output 规范都塞进去，依靠 LLM 的注意力机制
                full_spec_context = specs.GENERAL_SPECS + "\n"
                for key, content in specs.FILE_SPECS.items():
                    full_spec_context += f"\n--- INPUT SPEC: {key} ---\n{content}\n"
                for key, content in specs.OUTPUT_SPECS.items():
                    full_spec_context += f"\n--- OUTPUT SPEC: {key} ---\n{content}\n"

                # 调用 Pydantic 强类型的 Generator Agent
                cases = self.generator.generate(
                    rule_json=json.dumps(rule, ensure_ascii=False),
                    interface_context=full_spec_context,
                    system_context=specs.SYSTEM_CONTEXT
                )
                
                for case in cases:
                    self._save_case_artifact(case, rule, r_file, batch_dir)

        logger.info(f"\n✅ Generation Complete. Artifacts stored in {batch_dir}")

    def _save_case_artifact(self, case_dict, source_rule, source_file, batch_dir):
        """
        将单个测试用例的所有要素（DB、Input、Output）保存为独立的文件结构。
        """
        case_id = case_dict.get('case_id', 'UNKNOWN_CASE')
        safe_case_id = "".join([c if c.isalnum() or c in ['_', '-'] else '_' for c in case_id])
        
        case_dir = os.path.join(batch_dir, safe_case_id)
        os.makedirs(case_dir, exist_ok=True)
        
        logger.info(f"      💾 Archiving Case: {case_id}")

        # 1. 保存元数据 (meta.json)
        metadata = {
            "case_id": case_id,
            "description": case_dict.get('desc'),
            "source_rule": source_rule,
            "source_file": source_file,
            "expected_keyword": case_dict.get('expected_keyword'),
            "timestamp": int(time.time())
        }
        with open(os.path.join(case_dir, "meta.json"), 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        # 2. 保存数据库快照 (db_snapshot)
        snapshot_dir = os.path.join(case_dir, "db_snapshot")
        os.makedirs(snapshot_dir, exist_ok=True)
        setup_state = case_dict.get('setup_state', {})
        
        if 'accounts' in setup_state:
            with open(os.path.join(snapshot_dir, "Accounts.json"), 'w', encoding='utf-8') as f:
                json.dump(setup_state['accounts'], f, indent=2, ensure_ascii=False)
        if 'holdings' in setup_state:
            with open(os.path.join(snapshot_dir, "Holdings.json"), 'w', encoding='utf-8') as f:
                json.dump(setup_state['holdings'], f, indent=2, ensure_ascii=False)

        # 3. 保存输入文件 (input_files)
        input_files_root = os.path.join(case_dir, "input_files")
        self._save_files(case_dict.get('input_files', []), input_files_root)

        # 4. 保存预期输出文件 (expected_output_files)
        output_files_root = os.path.join(case_dir, "expected_output_files")
        self._save_files(case_dict.get('output_files', []), output_files_root)

    def _save_files(self, file_list, root_dir):
        """辅助方法：保存文件列表（适配 Pydantic dump 后的 dict 结构）"""
        if not file_list:
            return

        for file_obj in file_list:
            file_path = file_obj.get('path')
            file_content = file_obj.get('content')
            
            if file_path and file_content:
                clean_path = file_path.lstrip("/").lstrip("\\")
                if clean_path.startswith("./"): clean_path = clean_path[2:]
                
                full_path = os.path.join(root_dir, clean_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(file_content)

    def _extract_json_from_text(self, text):
        """辅助方法：从 Agent 的自然语言回复中提取 JSON List"""
        try:
            return json5.loads(text)
        except json5.JSONDecodeError as e:
            print(e)
            pass
        
        match = re.search(r"```json(.*?)```", text, re.DOTALL)
        if match:
            try:
                return json5.loads(match.group(1))
            except json5.JSONDecodeError:
                pass
        
        match = re.search(r"(\[.*\])", text, re.DOTALL)
        if match:
            try:
                return json5.loads(match.group(1))
            except:
                pass
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Agent for TA System Testing (Industrial Grade)")
    parser.add_argument("--step", choices=["analyze", "execute"], required=True, 
                        help="Choose 'analyze' (Phase 0+1) or 'execute' (Phase 2)")
    parser.add_argument("--reindex", action="store_true", help="Re-ingest knowledge base")
    parser.add_argument("--topics", nargs="+", help="Manually specify topics (overrides auto-planning)")
    
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    app = Orchestrator()
    app.initialize(reindex=args.reindex)

    if args.step == "analyze":
        # 如果没有指定 topics，则自动规划
        target_topics = args.topics if args.topics else app.phase_0_plan()
        app.phase_1_analyze(target_topics)
        
    elif args.step == "execute":
        app.phase_2_execute()
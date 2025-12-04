import argparse
import os
import json
import time
import shutil
import logging
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import langchain
from dotenv import load_dotenv

import config
import specs
from infrastructure import MockDBManager
from rag_service import UnifiedRAGService
from java_connector import JavaSUTConnector
from agents import BusinessRuleAnalyst, TestCaseGenerator

load_dotenv()

# 设置 Logger
logger = logging.getLogger("TA_Agent_Orchestrator")

SUPPORTED_FILE_TYPES = [
    "DIST_ACC - 销售商账户申请文件",
    "DIST_TRADE - 销售商交易申请文件",
    "MGR_NAV - 管理人净值文件",
    "MGR_APPLY - 管理人待确认文件"
    "DIST_ACC_CONFIRM - 销售商账户确认文件",
    "MGR_CONFIRM - 管理人确认文件",
    "DIST_CONFIRM - 销售商交易确认文件"
]

class TestStrategyPlanner:
    """
    [Phase 0 Agent] 测试战略规划师
    职责：综合阅读系统文档与核心代码逻辑，利用发散思维生成全面的测试主题列表。
    """
    def __init__(self, llm, retriever):
        self.llm = llm
        self.retriever = retriever

    def plan_test_campaign(self) -> list[str]:
        logger.info("🧠 Brainstorming test scenarios based on Specs AND Code Reality...")
        
        # 1. 主动检索代码层面的逻辑线索
        code_context = ""
        try:
            # 使用宽泛但针对逻辑的查询词，旨在捞取 Validate, Exception, Rule 等核心代码
            # 这样 Agent 就能看到文档没写的细节（例如代码里是否有 VIP 用户判断？是否有金额上限？）
            search_query = "Business validation logic rules constraints exception handling"
            logger.info(f"   🔍 Scanning codebase for: '{search_query}'")
            
            docs = self.retriever.invoke(search_query)
            
            # 格式化检索到的代码片段
            fragments = []
            for d in docs:
                source = d.metadata.get('source', 'unknown_file')
                content = d.page_content[:1000] # 截取前1000字符避免Token溢出
                fragments.append(f"--- Code Snippet from {source} ---\n{content}\n")
            
            code_context = "\n".join(fragments)
            logger.info(f"   -> Retrieved {len(docs)} code fragments to inform strategy.")
            
        except Exception as e:
            logger.warning(f"   ⚠️ Failed to retrieve code context, planning based on docs only. Error: {e}")

        # 2. 战略规划 Prompt
        template = """You are a Principal QA Architect for a Mission-Critical Financial System (Transfer Agent).
        Your goal is to design a comprehensive **Test Strategy** (List of Topics) to uncover hidden bugs and discrepancies.

        ### 1. SYSTEM DOCUMENTATION (The Theory)
        {system_context}

        ### 2. CODE SIGNALS (The Reality)
        Below are snippets from the actual codebase. Use them to identify:
        - **Undocumented Logic**: Logic present in code but missing in docs (e.g., Hidden limits, VIP lists).
        - **Defensive Checks**: Specific `if` conditions or Exceptions thrown in code.
        - **Discrepancies**: Where Code implementation differs from Specs.
        
        Code Reality Context:
        {code_context}

        ### 3. INTERFACE SURFACE (The Attack Vectors)
        The system accepts these file types:
        {file_types}

        ### 4. STRATEGY GENERATION
        Combine Docs and Code insights to generate 5-10 distinct, high-value **Test Topics**.
        
        Prioritize:
        1. **Gap Analysis**: Topics that verify if code matches docs.
        2. **Boundary Attacks**: Based on actual thresholds found in code (or implied).
        3. **Process Interaction**: Complex state transitions.
        
        Example Output:
        ["Redemption > 1M manual check logic", "Duplicate Account Opening Attempt", "Nav file missing for T-day"]

        Output JSON List:
        """
        
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | self.llm | JsonOutputParser()
        
        try:
            # 提取文件类型的名称供 Agent 参考
            file_type_names = [t.split(' - ')[0] for t in SUPPORTED_FILE_TYPES]
            
            topics = chain.invoke({
                "system_context": specs.SYSTEM_CONTEXT,
                "code_context": code_context,
                "file_types": ", ".join(file_type_names)
            })
            
            logger.info(f"🧠 Strategy Planner generated {len(topics)} topics.")
            return topics
        except Exception as e:
            logger.error(f"Failed to plan test strategy: {e}", exc_info=True)
            # Fallback topics
            return ["Redeem insufficient shares check", "Duplicate account opening check"]

class Orchestrator:
    def __init__(self):
        # 提高温度以增加发散性
        self.llm = ChatOpenAI(model=config.OPENAI_MODEL, temperature=0.7) 
        self.db_manager = MockDBManager()
        self.rag = UnifiedRAGService()
        self.java_sut = JavaSUTConnector()
        
        # Agents - 将在 initialize 中实例化
        self.planner = None
        self.analyst = None
        self.generator = None

    def initialize(self, reindex: bool = False):
        logger.info("Initializing Orchestrator...")
        if reindex:
            logger.info("Triggering Knowledge Base Ingestion...")
            self.rag.ingest_knowledge_base()
        
        retriever = self.rag.get_retriever()
        
        # Phase 0: 战略规划 Agent (高 Temperature, 读代码+文档)
        self.planner = TestStrategyPlanner(self.llm, retriever)
        
        # Phase 1 & 2: 分析与生成 Agent (低 Temperature, 保证严谨)
        precise_llm = ChatOpenAI(model=config.OPENAI_MODEL, temperature=0)
        self.analyst = BusinessRuleAnalyst(precise_llm, retriever)
        self.generator = TestCaseGenerator(precise_llm)
        
        os.makedirs(config.RULES_DIR, exist_ok=True)
        logger.info("Initialization complete. Agents ready.")

    def phase_0_plan(self):
        """阶段零：自动策划测试战役"""
        if not self.planner:
            logger.error("System not initialized.")
            return []

        logger.info("🚀 === PHASE 0: STRATEGY PLANNING ===")
        topics = self.planner.plan_test_campaign()
        
        logger.info("📋 Generated Test Plan:")
        for i, t in enumerate(topics):
            logger.info(f"   {i+1}. {t}")
        
        return topics

    def phase_1_analyze(self, topics):
        """阶段一：分析文档和代码，提取规则供人工审核"""
        if not self.analyst:
            logger.error("System not initialized. Call initialize() first.")
            return

        logger.info("\n🚀 === PHASE 1: ANALYSIS & EXTRACTION ===")
        logger.info(f"Analyzing {len(topics)} topics...")

        for topic in topics:
            logger.info(f"👉 Analyzing Topic: {topic}")
            try:
                rules = self.analyst.analyze(topic)
                
                # 文件名增加 safe 处理
                safe_topic = "".join([c if c.isalnum() else '_' for c in topic])
                filename = f"rules_{int(time.time())}_{safe_topic[:50]}.json"
                filepath = os.path.join(config.RULES_DIR, filename)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(rules, f, indent=2, ensure_ascii=False)
                
                logger.info(f"✅ Rules extracted to: {filepath}")
            except Exception as e:
                logger.error(f"❌ Failed to analyze topic '{topic}': {e}", exc_info=True)

    def _identify_required_files(self, rule):
        logger.debug(f"Identifying required file types for rule: {rule.get('rule_id', 'UNKNOWN')}...")
        
        template = """You are a QA Architect.
        Identify required Interface Files for this rule based on V1.0 Spec.
        
        Rule: {rule}
        Available Types: {file_types}
        
        Return JSON list of keys (e.g., ["DIST_TRADE", "MGR_NAV"]).
        """
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | self.llm | JsonOutputParser()
        try:
            available_keys = [t.split(' - ')[0] for t in SUPPORTED_FILE_TYPES]
            result_keys = chain.invoke({
                "rule": str(rule),
                "file_types": json.dumps(SUPPORTED_FILE_TYPES, ensure_ascii=False)
            })
            valid_keys = [k for k in result_keys if k in available_keys]
            
            logger.info(f"-> Agent identified input files: {valid_keys}")
            return valid_keys
        except Exception as e:
            logger.warning(f"Identification failed, falling back to default. Error: {e}")
            return ["DIST_TRADE"]

    def phase_2_execute(self):
        """阶段二：生成测试用例并进行独立归档存储"""
        if not self.generator:
            logger.error("System not initialized.")
            return

        logger.info("\n🚀 === PHASE 2: GENERATION & ARTIFACT STORAGE (V1.0 Spec) ===")
        
        try:
            rule_files = [f for f in os.listdir(config.RULES_DIR) if f.endswith(".json")]
        except FileNotFoundError:
            logger.error(f"Rules directory not found: {config.RULES_DIR}")
            return

        if not rule_files:
            logger.error(f"No rule files found in {config.RULES_DIR}. Please run Phase 1 first.")
            return
        
        # 创建本次运行的批次目录
        batch_id = f"batch_{int(time.time())}"
        batch_dir = os.path.join(config.DATA_DIR, "generated_batches", batch_id)
        os.makedirs(batch_dir, exist_ok=True)
        logger.info(f"📂 Output Batch Directory created: {batch_dir}")

        for r_file in rule_files:
            r_path = os.path.join(config.RULES_DIR, r_file)
            logger.info(f"📂 Processing Rule File: {r_file}")
            
            try:
                with open(r_path, 'r', encoding='utf-8') as f:
                    rules = json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to load JSON from {r_file}: {e}")
                continue
            
            for rule in rules:
                rule_id = rule.get('rule_id', 'UNKNOWN')
                logger.info(f"⚡ Generating Cases for Rule [{rule_id}]: {rule.get('logic', '')[:50]}...")
                
                # 1. 确定输入文件
                target_file_keys = self._identify_required_files(rule)
                
                # 2. 组装上下文
                full_context = specs.SYSTEM_CONTEXT + "\n" + specs.GENERAL_SPECS + "\n"
                for key in target_file_keys:
                    specific_spec = specs.FILE_SPECS.get(key)
                    if specific_spec:
                        full_context += f"\n--- SPEC FOR {key} ---\n{specific_spec}\n"
                full_context += "\n--- OUTPUT FILE REFERENCE ---\n" + str(specs.OUTPUT_SPECS)

                # 3. 生成用例
                logger.debug(f"Invoking Generator Agent for Rule {rule_id}...")
                try:
                    cases = self.generator.generate(
                        rule, 
                        interface_context=full_context,
                        system_context=specs.SYSTEM_CONTEXT
                    )
                    logger.info(f"-> Generated {len(cases)} cases for Rule {rule_id}")
                except Exception as e:
                    logger.error(f"Failed to generate cases for Rule {rule_id}: {e}", exc_info=True)
                    continue
                
                # 4. 独立归档存储每个用例
                for case in cases:
                    self._save_case_artifact(case, rule, r_file, batch_dir)

        logger.info(f"✅ All test cases have been generated and archived in: {batch_dir}")

    def _save_case_artifact(self, case, rule, source_file, batch_dir):
        """
        将单个测试用例的所有要素（DB、Input、Output）保存为独立的文件结构。
        """
        case_id = case.get('case_id', 'UNKNOWN_CASE')
        safe_case_id = "".join([c if c.isalnum() or c in ['_', '-'] else '_' for c in case_id])
        
        case_dir = os.path.join(batch_dir, safe_case_id)
        os.makedirs(case_dir, exist_ok=True)
        
        logger.info(f"      💾 Archiving Case: {case_id} -> {case_dir}")

        # 1. 保存元数据 (meta.json)
        metadata = {
            "case_id": case_id,
            "description": case.get('desc'),
            "source_rule_id": rule.get('rule_id'),
            "source_rule_logic": rule.get('logic'),
            "source_rule_file": source_file,
            "expected_keyword": case.get('expected_keyword'),
            "timestamp": int(time.time())
        }
        with open(os.path.join(case_dir, "meta.json"), 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        # 2. 保存数据库快照 (db_snapshot)
        snapshot_dir = os.path.join(case_dir, "db_snapshot")
        os.makedirs(snapshot_dir, exist_ok=True)
        setup_state = case.get('setup_state', {})
        
        if 'accounts' in setup_state:
            with open(os.path.join(snapshot_dir, "Accounts.json"), 'w', encoding='utf-8') as f:
                json.dump(setup_state['accounts'], f, indent=2, ensure_ascii=False)
        if 'holdings' in setup_state:
            with open(os.path.join(snapshot_dir, "Holdings.json"), 'w', encoding='utf-8') as f:
                json.dump(setup_state['holdings'], f, indent=2, ensure_ascii=False)

        # 3. 保存输入文件 (input_files)
        input_files_root = os.path.join(case_dir, "input_files")
        self._save_files(case.get('input_files', []), input_files_root, "input")

        # 4. 保存预期输出文件 (expected_output_files)
        output_files_root = os.path.join(case_dir, "expected_output_files")
        self._save_files(case.get('output_files', []), output_files_root, "output")

    def _save_files(self, file_list, root_dir, type_tag):
        """辅助方法：保存文件列表到指定目录"""
        # 兼容旧格式（单文件）
        if not isinstance(file_list, list): 
            return 

        for file_obj in file_list:
            file_path = file_obj.get('path')
            file_content = file_obj.get('content')
            
            if file_path and file_content:
                clean_path = file_path.lstrip("/").lstrip("\\")
                if clean_path.startswith("./"):
                    clean_path = clean_path[2:]
                
                full_path = os.path.join(root_dir, clean_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(file_content)
                logger.debug(f"        -> Saved {type_tag} file: {clean_path}")

    def execute_case(self, case):
        pass 

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", choices=["analyze", "execute"], required=True, 
                        help="Choose 'analyze' to generate rules, or 'execute' to generate test cases.")
    parser.add_argument("--reindex", action="store_true")
    parser.add_argument("--debug", action="store_true", help="Enable full LangChain debug logging")
    parser.add_argument("--topics", nargs="+", help="Manually specify topics (overrides auto-planning)")
    
    args = parser.parse_args()

    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    if args.debug:
        print("🐛 Debug mode enabled: Monitoring all LLM inputs and outputs.")
        try:
            from langchain.globals import set_debug
            set_debug(True)
        except ImportError:
            langchain.debug = True
        logging.basicConfig(level=logging.DEBUG, format=log_format)
    else:
        logging.basicConfig(level=logging.INFO, format=log_format)

    app = Orchestrator()
    try:
        app.initialize(reindex=args.reindex)

        if args.step == "analyze":
            # 逻辑变更：如果有手动 Topics 则使用，否则进行自动规划 (Phase 0)
            if args.topics:
                target_topics = args.topics
                logger.info(f"📋 Using Manual Topics: {target_topics}")
            else:
                target_topics = app.phase_0_plan()
            
            # 进入 Phase 1
            app.phase_1_analyze(target_topics)
            
        elif args.step == "execute":
            app.phase_2_execute()
            
    except Exception as e:
        logger.critical(f"Unhandled exception in main execution: {e}", exc_info=True)
from typing import List, Dict
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnablePassthrough

class BusinessRuleAnalyst:
    """业务规则提取 Agent (文档 + 代码)"""
    def __init__(self, llm, retriever):
        self.llm = llm
        self.retriever = retriever

    def analyze(self, topic: str) -> List[Dict]:
        print(f"\n🕵️ [Analyst] Analyzing Docs & Code for: {topic}")
        template = """You are a Senior QA Architect.
        Extract business rules for "{topic}" from the retrieved context.
        
        Context:
        {context}
        
        Output JSON list:
        [
            {{
                "rule_id": "Unique ID",
                "logic": "Description",
                "condition": "Condition"
            }}
        ]
        """
        prompt = ChatPromptTemplate.from_template(template)
        chain = (
            {"context": self.retriever, "topic": RunnablePassthrough()}
            | prompt
            | self.llm
            | JsonOutputParser()
        )
        try:
            return chain.invoke(topic)
        except Exception as e:
            print(f"   ⚠️ Analysis error: {e}")
            return []

class TestCaseGenerator:
    """测试用例生成 Agent (增强版：注入系统认知与格式强校验，支持输入/输出多文件)"""
    def __init__(self, llm):
        self.llm = llm

    def generate(self, rule: Dict, interface_context: str = "", system_context: str = "") -> List[Dict]:
        template = """You are an expert SDET for a Fund Transfer Agent (TA) system.
        Your task is to generate a comprehensive test case including DB State, Input Files, AND **Expected Output Files**.

        ### 1. THE GOAL
        Target Rule: {rule_json}

        ### 2. SYSTEM KNOWLEDGE (The Brain)
        Use this logic to ensure data consistency:
        {system_context}

        ### 3. INTERFACE SPECIFICATIONS (The Format)
        Strictly follow these file definitions.
        **CRITICAL: EVERY CSV FILE (INPUT & OUTPUT) MUST HAVE A HEADER ROW.**
        {interface_context}

        ### 4. GENERATION TASK
        Generate a JSON object with a 'cases' list. Each case must include:
        
        1. `case_id`: e.g., "TC_RED_001"
        2. `desc`: Description of the test scenario.
        3. `setup_state`: The T-1 DB state (Accounts, Holdings).
        4. `input_files`: List of input file objects.
             - `path`: e.g., `input/20231027/DIST_A_TRADE_FUND01_20231027.csv`.
             - `content`: Exact CSV content with HEADER.
        5. `output_files`: **A LIST of EXPECTED output file objects**.
             - `path`: e.g., `output/20231027/TO_DIST_CONFIRM_20231027.csv`.
             - `content`: The EXACT expected CSV content with HEADER.
             - **LOGIC**: Based on the rule (e.g., if input has invalid ID, output status='0', message='ID_NOT_FOUND').
        6. `expected_keyword`: A specific error code/status for quick check.

        JSON Output:
        """
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | self.llm | JsonOutputParser()
        try:
            res = chain.invoke({
                "rule_json": str(rule),
                "interface_context": interface_context,
                "system_context": system_context
            })
            return res.get("cases", [])
        except Exception as e:
            print(f"   ⚠️ Generator error: {e}")
            return []
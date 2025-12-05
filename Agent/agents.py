from typing import List, Optional, Dict
from langchain.agents import create_agent
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
# 切换为 Google Gemini 的官方集成
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
# Robust import for AgentExecutor
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain.agents.structured_output import ToolStrategy

from tools import lookup_business_rules, get_system_context
import config

# ==========================================
# 1. Pydantic Schema Definitions (Data Contracts)
# ==========================================

class FileArtifact(BaseModel):
    path: str = Field(description="Relative path, e.g., input/20231027/REQ.csv")
    content: str = Field(description="File content including headers")

class TestCase(BaseModel):
    case_id: str = Field(description="Unique ID, e.g., TC_RED_001")
    desc: str = Field(description="Description of the test scenario")
    setup_state: dict = Field(description="T-1 DB State (Accounts, Holdings)")
    input_files: List[FileArtifact] = Field(description="List of input files for T-day")
    output_files: List[FileArtifact] = Field(description="List of EXPECTED output files")
    expected_keyword: str = Field(description="Verification keyword for quick check")

class TestCaseList(BaseModel):
    cases: List[TestCase]

class TestStrategy(BaseModel):
    topics: List[str] = Field(description="List of 5-8 distinct, high-value test topics")

class BusinessRule(BaseModel):
    rule_id: str = Field(description="Unique Rule ID, e.g., RULE_001")
    logic: str = Field(description="Human readable description of the business logic")
    condition: str = Field(description="Technical condition or constraint")

class BusinessRuleList(BaseModel):
    rules: List[BusinessRule]

# ==========================================
# 2. Agent Definitions (Provider Strategy Edition)
# ==========================================

class TestStrategyPlannerAgent:
    """[Phase 0] 战略规划师: 使用 Provider Strategy (Native Structured Output)"""
    def __init__(self, model_name: str = "gemini-1.5-pro"):
        # 使用较高的 Temperature 以激发发散性思维
        # self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=0.7)
        self.llm = ChatOpenAI(model=model_name, temperature=0.7)
    def plan(self, system_context: str, file_interfaces: str) -> List[str]:
        # Provider Strategy: 直接绑定 Schema，由 Gemini 原生强制输出结构
        structured_llm = self.llm.with_structured_output(TestStrategy)
        
        template = """You are a Principal QA Architect for a Mission-Critical Financial System (Transfer Agent).
        Your goal is to design a comprehensive **Test Strategy** (List of Topics) to uncover hidden bugs.

        ### 1. SYSTEM CONTEXT
        {system_context}

        ### 2. FILE INTERFACES
        The system handles these files: {file_types}

        ### 3. BRAINSTORMING METHODOLOGY
        Do not just test happy paths. You must apply:
        - **Boundary Value Analysis**: Test max/min amounts, zero values, extreme dates.
        - **Equivalence Partitioning**: Valid vs Invalid status, Supported vs Unsupported types.
        - **Error Guessing**: Duplicate IDs, Missing fields, Logic conflicts (Redeem > Balance).
        - **Process Interaction**: Open account then trade immediately (T0), Trade on non-existent account.

        ### 4. OUTPUT REQUIREMENT
        Generate a list of 5-8 distinct, high-value **Test Topics** (Strings).
        """
        
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | structured_llm
        
        try:
            res = chain.invoke({
                "system_context": system_context,
                "file_types": file_interfaces
            })
            # 直接返回 Pydantic 对象解析后的数据
            return res.topics
        except Exception as e:
            print(f"⚠️ Strategy Planning failed: {e}")
            return ["Redemption validation logic", "Account status checks"]

class BusinessRuleAnalystAgent:
    """[Phase 1] 规则分析师: Tool Calling Loop + Provider Strategy Extraction"""
    def __init__(self):
        # self.llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0)
        self.llm = ChatOpenAI(model=config.OPENAI_MODEL, temperature=0)
        self.tools = [lookup_business_rules, get_system_context]
        
        # 1. 调研阶段：使用 Tool Calling Agent (ReAct) 进行自由探索
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a Senior QA Architect. Investigate the topic thoroughly using your tools."),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ])
        
        agent = create_tool_calling_agent(self.llm, self.tools, prompt)
        self.research_executor = AgentExecutor(agent=agent, tools=self.tools, verbose=False)
        
        # 2. 提取阶段：使用 Provider Strategy 进行结构化提取
        self.extractor_llm = self.llm.with_structured_output(BusinessRuleList)

    def analyze(self, topic: str) -> List[dict]:
        # Step 1: Research (Unstructured Thinking)
        try:
            research_res = self.research_executor.invoke({
                "input": f"Research all business rules and constraints for: '{topic}'. "
                         f"Check Documentation and Code. Summarize findings."
            })
            findings = research_res['output']
        except Exception as e:
            print(f"⚠️ Research failed: {e}")
            findings = f"Analyze logic for {topic} based on general context."

        # Step 2: Extraction (Native Structured Output)
        extract_prompt = ChatPromptTemplate.from_template("""
        Based on the following research findings, extract formal Business Rules.
        
        ### FINDINGS
        {findings}
        
        Extract a list of rules corresponding to the findings.
        """)
        
        chain = extract_prompt | self.extractor_llm
        
        try:
            res = chain.invoke({"findings": findings})
            return [rule.model_dump() for rule in res.rules]
        except Exception as e:
            print(f"⚠️ Rule Extraction failed: {e}")
            return []

class TestCaseGeneratorAgent:
    """[Phase 2] 用例生成器: 使用 Parser 手动解析"""
    def __init__(self, model_name: str = "gemini-3-pro"):
        self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=0)

    def generate(self, rule_json: str, interface_context: str = "", system_context: str = "") -> List[dict]:
        # 1. 定义 Parser
        parser = JsonOutputParser(pydantic_object=TestCaseList)
        
        prompt = ChatPromptTemplate.from_template("""
        You are an expert SDET. Generate comprehensive test cases for the rule below.

        ### 1. TARGET RULE
        {rule}

        ### 2. SYSTEM KNOWLEDGE
        {system_context}

        ### 3. INTERFACE SPECIFICATIONS
        Strictly follow these definitions for file formats (CSV Headers, naming conventions):
        {interface_context}

        ### 4. TASK
        Generate valid JSON test cases. Ensure:
        - `input_files` match the Spec.
        - `setup_state` supports the scenario (Dependency Chain).
        - `output_files` represent the expected system response.
        
        {format_instructions}
        """,
        partial_variables={"format_instructions": parser.get_format_instructions()}
        )
        
        chain = prompt | self.llm | parser
        
        try:
            res = chain.invoke({
                "rule": rule_json,
                "interface_context": interface_context,
                "system_context": system_context
            })
            # res 是 {'cases': [...]}
            return res.get("cases", [])
        except Exception as e:
            print(f"⚠️ Case Gen failed: {e}")
            return []
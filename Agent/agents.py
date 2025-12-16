from typing import List, Optional, Dict
from langchain.agents import create_agent
from langchain_core.output_parsers import JsonOutputParser, format_instructions
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
    path: str = Field(description="文件相对路径，例如 input/20231027/REQ.csv")
    content: str = Field(description="包含表头在内的完整文件内容")

class TestCase(BaseModel):
    case_id: str = Field(description="用例唯一ID，例如 TC_RED_001")
    desc: str = Field(description="测试场景的中文描述")
    setup_state: dict = Field(description="T-1 数据库状态（Accounts, Holdings）")
    input_files: List[FileArtifact] = Field(description="T日输入文件列表")
    output_files: List[FileArtifact] = Field(description="预期输出文件列表")
    expected_keyword: str = Field(description="用于快速校验的关键字")

class TestCaseList(BaseModel):
    cases: List[TestCase]

class TestStrategy(BaseModel):
    topics: List[str] = Field(description="5-8 个高价值的测试主题（中文）")

class BusinessRule(BaseModel):
    rule_id: str = Field(description="规则唯一标识，例如 RULE_001")
    logic: str = Field(description="业务逻辑的中文描述")
    condition: str = Field(description="技术条件或约束的中文表述")

class BusinessRuleList(BaseModel):
    rules: List[BusinessRule]

# ==========================================
# 2. Agent Definitions (Provider Strategy Edition)
# ==========================================

class TestStrategyPlannerAgent:
    """[Phase 0] 战略规划师: 使用 Provider Strategy (Native Structured Output)"""
    def __init__(self, model_name: str = "gemini-1.5-pro"):
        # 使用较高的 Temperature 以激发发散性思维
        self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=0.7, timeout=10000)
        # self.llm = ChatOpenAI(model=model_name, temperature=0.7)
    def plan(self, system_context: str, file_interfaces: str) -> List[str]:
        # Provider Strategy: 直接绑定 Schema，由 Gemini 原生强制输出结构
        structured_llm = self.llm.with_structured_output(TestStrategy)
        
        template = """你是一名服务于关键金融系统（登记过户TA）的资深测试架构师。
        目标：设计覆盖漏洞的**测试主题列表**（5-8条），确保严谨性与广度。

        ### 1. 系统上下文
        {system_context}

        ### 2. 文件接口
        系统处理的文件类型：{file_types}

        ### 3. 思考方法
        不只验证正向路径，务必应用：
        - **边界值分析**：最大/最小金额、零值、极端日期。
        - **等价类划分**：合法/非法状态，支持/不支持的类型。
        - **错误猜测**：重复ID、缺失字段、逻辑冲突（赎回>可用份额）。
        - **流程交互**：开户即刻交易（T0）、不存在账户的交易。

        ### 4. 输出要求
        用中文给出5-8个高价值的测试主题（字符串列表），主题表述清晰、可执行。
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
            return ["赎回校验规则", "账户状态校验"]

class BusinessRuleAnalystAgent:
    """[Phase 1] 规则分析师: Tool Calling Loop + Provider Strategy Extraction"""
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(model="gemini-3-pro-preview", temperature=0, timeout=10000)
        # self.llm = ChatOpenAI(model=config.OPENAI_MODEL, temperature=0)
        self.tools = [lookup_business_rules, get_system_context]
        
        # 1. 调研阶段：使用 Tool Calling Agent (ReAct) 进行自由探索
        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一名高级QA架构师。请充分使用可用工具深入调研，回答必须使用中文。"),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ])
        
        agent = create_tool_calling_agent(self.llm, self.tools, prompt)
        self.research_executor = AgentExecutor(agent=agent, tools=self.tools, verbose=True)
        
        # 2. 提取阶段：使用 Provider Strategy 进行结构化提取
        self.extractor_parser = JsonOutputParser(pydantic_object=BusinessRuleList)

    def analyze(self, topic: str) -> List[dict]:
        # Step 1: Research (Unstructured Thinking)
        try:
            research_res = self.research_executor.invoke({
                "input": f"调研主题「{topic}」的全部业务规则与约束，查阅文档和代码并用中文总结。"
            })
            findings = research_res['output']
        except Exception as e:
            print(f"⚠️ Research failed: {e}")
            findings = f"基于通用上下文分析主题「{topic}」的逻辑。"

        # Step 2: Extraction (Native Structured Output)
        # Use template variables instead of f-string injection to avoid accidental
        # placeholder parsing when findings text contains braces (e.g. JSON with `{type}`).
        extract_prompt = ChatPromptTemplate.from_template(
            """
            请基于以下调研结论提取正式的业务规则，输出中文描述。

            ### 调研结论
            {find}

            参照如下的格式，给出规则列表。
            {format_instructions}
            """,
            partial_variables={
                "format_instructions": self.extractor_parser.get_format_instructions()
            },
        )
        
        chain = extract_prompt | self.llm | self.extractor_parser
        
        try:
            print(findings)
            res = chain.invoke({
                "find": findings
            })
            return res.get("rules", [])
        except Exception as e:
            print(f"⚠️ Rule Extraction failed: {e}")
            return []

class TestCaseGeneratorAgent:
    """[Phase 2] 用例生成器: 使用 Parser 手动解析"""
    def __init__(self, model_name: str = "gemini-3-pro"):
        self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=0, timeout=10000)

    def generate(self, rule_json: str, interface_context: str = "", system_context: str = "") -> List[dict]:
        # 1. 定义 Parser
        parser = JsonOutputParser(pydantic_object=TestCaseList)
        
        prompt = ChatPromptTemplate.from_template("""
        你是一名资深SDET，请为下述规则生成全面的测试用例。但字段名保持原样。

        ### 1. 目标规则
        {rule}

        ### 2. 系统知识
        {system_context}

        ### 3. 接口规范
        严格遵循以下文件格式与命名（CSV表头、路径等）：
        {interface_context}

        ### 4. 任务
        生成合法的 JSON 测试用例，确保：
        - `input_files` 符合规范。
        - `setup_state` 能支撑场景依赖。
        - `output_files` 反映预期系统行为。
        
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
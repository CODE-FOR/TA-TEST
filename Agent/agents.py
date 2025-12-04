from typing import List, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from tools import lookup_business_rules, get_file_spec_definition, get_system_context
import config

# --- 1. 定义结构化输出 (Schema Engineering) ---
# 这是 MCP 思想的体现：定义明确的数据契约

class FileArtifact(BaseModel):
    path: str = Field(description="Relative path, e.g., input/20231027/REQ.csv")
    content: str = Field(description="File content including headers")

class TestCase(BaseModel):
    case_id: str = Field(description="Unique ID, e.g., TC_RED_001")
    desc: str = Field(description="Description of the test scenario")
    setup_state: dict = Field(description="T-1 DB State (Accounts, Holdings)")
    input_files: List[FileArtifact] = Field(description="List of input files for T-day")
    output_files: List[FileArtifact] = Field(description="List of EXPECTED output files")
    expected_keyword: str = Field(description="Verification keyword")

class TestCaseList(BaseModel):
    cases: List[TestCase]

# --- 2. 真正的 Agent: BusinessRuleAnalyst ---
# 这个 Agent 能够自主决定查什么资料

class BusinessRuleAnalystAgent:
    def __init__(self):
        self.llm = ChatOpenAI(model=config.OPENAI_MODEL, temperature=0)
        self.tools = [lookup_business_rules, get_system_context]
        
        # 标准 LangChain Agent 构造
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a Senior QA Architect. Analyze the topic to extract business rules."),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ])
        
        agent = create_tool_calling_agent(self.llm, self.tools, prompt)
        self.executor = AgentExecutor(agent=agent, tools=self.tools, verbose=True)

    def analyze(self, topic: str):
        # 让 Agent 自己去思考怎么查资料
        response = self.executor.invoke({
            "input": f"Analyze the topic '{topic}'. Extract business rules. "
                     f"First check system context, then search for specific rules. "
                     f"Output the rules in a clean JSON format."
        })
        # 注意：这里返回的是 Agent 的最终回复字符串，如果需要结构化，
        # 可以再接一个 StructuredOutputParser，或者让 Agent 调用一个 save_rules 的 tool
        return response["output"]

# --- 3. 结构化生成器: TestCaseGenerator ---
# 这里使用 with_structured_output，这是目前最稳定的生成 JSON 的方式

class TestCaseGeneratorAgent:
    def __init__(self):
        self.llm = ChatOpenAI(model=config.OPENAI_MODEL, temperature=0)

    def generate(self, rule_json: str) -> List[dict]:
        # 绑定 Pydantic 模型，强制 LLM 输出符合 Schema 的数据
        structured_llm = self.llm.with_structured_output(TestCaseList)
        
        # 可以在 Prompt 中告知 LLM 可以调用 tools 来获取文件规范，
        # 或者直接把规范注入到 Prompt Context 中（如果规范较短）。
        # 为了展示 Tool Calling，我们这里也可以 bind tools，但 structured_output 互斥。
        # 更好的做法是 RAG 取回规范，放在 Context 里，然后强制结构化输出。
        
        prompt = ChatPromptTemplate.from_template("""
        You are an SDET. Generate test cases for the following rule.
        
        Rule: {rule}
        
        Reference Specs:
        {specs}
        
        Generate strict JSON.
        """)
        
        # 简单的做法：预先取回 Spec (或者让上游传进来)
        # 这里为了演示方便，我们假设 specs 已经通过某种方式获取了，
        # 或者我们可以写一个 Chain：先查 Spec，再生成。
        
        # 为了演示 "Tool Calling 思想"，我们这里做一个 Hybrid：
        # 实际工程中，通常会在 Chain 的前序步骤准备好 Context。
        
        import specs as static_specs # 暂时引用静态，实际应动态获取
        
        chain = prompt | structured_llm
        
        result = chain.invoke({
            "rule": rule_json,
            "specs": str(static_specs.FILE_SPECS) # 简单粗暴注入，工业级应使用 RAG
        })
        
        # Pydantic 转 Dict
        return [c.model_dump() for c in result.cases]
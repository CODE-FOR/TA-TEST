from langchain_core.tools import tool
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
import config
import specs

# 初始化 RAG (复用之前的逻辑，但在 Tool 中懒加载)
def get_retriever():
    embeddings = OpenAIEmbeddings(model=config.EMBEDDING_MODEL)
    vector_store = Chroma(
        persist_directory=config.VECTOR_DB_PATH, 
        embedding_function=embeddings,
        collection_name="ta_unified_kb"
    )
    return vector_store.as_retriever(search_kwargs={"k": 5})

@tool
def lookup_business_rules(query: str) -> str:
    """
    在QA知识库（文档与代码）中检索业务规则、校验逻辑与系统约束。
    适用于需要理解系统运作方式的场景。回答请使用中文。
    """
    retriever = get_retriever()
    docs = retriever.invoke(query)
    return "\n\n".join([f"Source: {d.metadata.get('source', 'unknown')}\nContent: {d.page_content}" for d in docs])

@tool
def get_file_spec_definition(file_type_key: str) -> str:
    """
    获取指定文件类型的详细接口规范。
    参数:
        file_type_key: 文件类型键，例如 'DIST_TRADE'、'MGR_NAV'、'DIST_ACC'。
    """
    spec = specs.FILE_SPECS.get(file_type_key)
    if spec:
        return spec
    return f"Error: No spec found for key '{file_type_key}'. Available keys: {list(specs.FILE_SPECS.keys())}"

@tool
def get_system_context() -> str:
    """获取系统的业务上下文、穿透式原则和每日批处理阶段说明。"""
    return specs.SYSTEM_CONTEXT
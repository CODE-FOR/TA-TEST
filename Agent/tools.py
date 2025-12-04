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
    Search the QA Knowledge Base (Docs & Code) for business rules, 
    validation logic, and system constraints.
    Useful when you need to understand HOW the system works.
    """
    retriever = get_retriever()
    docs = retriever.invoke(query)
    return "\n\n".join([f"Source: {d.metadata.get('source', 'unknown')}\nContent: {d.page_content}" for d in docs])

@tool
def get_file_spec_definition(file_type_key: str) -> str:
    """
    Get the detailed Interface Specification for a specific file type.
    Args:
        file_type_key: The key of the file type, e.g., 'DIST_TRADE', 'MGR_NAV', 'DIST_ACC'.
    """
    spec = specs.FILE_SPECS.get(file_type_key)
    if spec:
        return spec
    return f"Error: No spec found for key '{file_type_key}'. Available keys: {list(specs.FILE_SPECS.keys())}"

@tool
def get_system_context() -> str:
    """Get the high-level system context, look-through principles, and operation phases."""
    return specs.SYSTEM_CONTEXT
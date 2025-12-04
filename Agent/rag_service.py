import os
import glob
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
import config

class UnifiedRAGService:
    def __init__(self):
        self.persist_directory = config.VECTOR_DB_PATH
        self.embeddings = OpenAIEmbeddings(model=config.EMBEDDING_MODEL)
        self.vector_store = None

    def ingest_knowledge_base(self):
        """同时加载 Java 代码和业务文档"""
        print(f"📚 [RAG] Ingesting Knowledge Base...")
        
        all_docs = []

        # 1. 加载 Java 代码
        if os.path.exists(config.JAVA_SOURCE_ROOT):
            print(f"   -> Loading Java Code from {config.JAVA_SOURCE_ROOT}...")
            java_loader = DirectoryLoader(
                config.JAVA_SOURCE_ROOT, glob="**/*.java", loader_cls=TextLoader
            )
            java_raw = java_loader.load()
            java_splitter = RecursiveCharacterTextSplitter.from_language(
                language=Language.JAVA, chunk_size=2000, chunk_overlap=200
            )
            java_chunks = java_splitter.split_documents(java_raw)
            # 标记元数据
            for doc in java_chunks:
                doc.metadata["source_type"] = "code"
            all_docs.extend(java_chunks)

        # 2. 加载业务文档 (md, txt)
        if os.path.exists(config.DOC_SOURCE_ROOT):
            print(f"   -> Loading Docs from {config.DOC_SOURCE_ROOT}...")
            # 也可以支持 PDFLoader，这里以 Text 为主
            doc_loader = DirectoryLoader(
                config.DOC_SOURCE_ROOT, glob="**/*.md", loader_cls=TextLoader
            )
            doc_raw = doc_loader.load()
            doc_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000, chunk_overlap=100
            )
            doc_chunks = doc_splitter.split_documents(doc_raw)
            # 标记元数据
            for doc in doc_chunks:
                doc.metadata["source_type"] = "document"
            all_docs.extend(doc_chunks)

        if not all_docs:
            print("⚠️ No documents or code found to ingest.")
            return

        # 3. 存入向量库
        self.vector_store = Chroma.from_documents(
            documents=all_docs,
            embedding=self.embeddings,
            persist_directory=self.persist_directory,
            collection_name="ta_unified_kb"
        )
        print(f"✅ [RAG] Ingestion complete. Total chunks: {len(all_docs)}")

    def get_retriever(self):
        if not self.vector_store:
            self.vector_store = Chroma(
                persist_directory=self.persist_directory, 
                embedding_function=self.embeddings,
                collection_name="ta_unified_kb"
            )
        
        # 增加搜索数量，确保能同时覆盖代码和文档
        return self.vector_store.as_retriever(
            search_type="mmr", 
            search_kwargs={"k": 6, "fetch_k": 20}
        )
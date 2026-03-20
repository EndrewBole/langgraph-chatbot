from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def split_products(docs: list[Document]) -> list[Document]:
    """Chunking para fichas de produto (descrições curtas)."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=256,
        chunk_overlap=32,
        separators=["\n\n", "\n", ".", " "],
    )
    return splitter.split_documents(docs)


def split_documents(docs: list[Document]) -> list[Document]:
    """Chunking para documentos longos (PDFs, manuais, Word)."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=512,
        chunk_overlap=80,
        separators=["\n\n", "\n", ".", " "],
    )
    return splitter.split_documents(docs)

"""
Script de ingestão de documentos para o RAG da Temporalis AI.

Uso:
    python scripts/ingest.py                  # indexa tudo de ./data
    python scripts/ingest.py --data-dir /caminho/para/pasta
    python scripts/ingest.py --clear           # limpa a tabela e reindexa

Formatos aceitos: PDF, CSV, XLSX, DOCX

Coloque os arquivos na pasta `data/` na raiz do projeto e execute.
"""

import argparse
import os
import sys

# Adiciona raiz do projeto ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import settings
from src.rag.loaders import load_all_from_dir, SUPPORTED_EXTENSIONS
from src.rag.splitters import split_products, split_documents
from src.rag.indexer import create_vectorstore, get_supabase_client


def classify_and_split(docs):
    """Separa documentos por tipo e aplica chunking adequado."""
    product_docs = []
    long_docs = []

    for doc in docs:
        file_type = doc.metadata.get("file_type", "")
        if file_type in ("csv", "xlsx"):
            product_docs.append(doc)
        else:
            long_docs.append(doc)

    chunks = []
    if product_docs:
        chunks.extend(split_products(product_docs))
    if long_docs:
        chunks.extend(split_documents(long_docs))

    return chunks


def main():
    parser = argparse.ArgumentParser(description="Ingestao de documentos para RAG Temporalis AI")
    parser.add_argument("--data-dir", default=settings.DATA_DIR, help="Pasta com arquivos para indexar")
    parser.add_argument("--clear", action="store_true", help="Limpa a tabela antes de reindexar")
    args = parser.parse_args()

    data_dir = args.data_dir

    if not os.path.exists(data_dir):
        print(f"[ERRO] Pasta '{data_dir}' nao encontrada.")
        print(f"Crie a pasta e adicione arquivos ({', '.join(SUPPORTED_EXTENSIONS)}).")
        sys.exit(1)

    files = [f for f in os.listdir(data_dir) if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS]
    if not files:
        print(f"[ERRO] Nenhum arquivo suportado encontrado em '{data_dir}'.")
        print(f"Formatos aceitos: {', '.join(SUPPORTED_EXTENSIONS)}")
        sys.exit(1)

    if args.clear:
        print("[INFO] Limpando tabela 'documents' no Supabase...")
        client = get_supabase_client()
        client.table("documents").delete().neq("id", 0).execute()
        print("[OK] Tabela limpa.")

    print(f"[INFO] Carregando arquivos de '{data_dir}'...")
    print(f"       Arquivos encontrados: {len(files)}")
    for f in files:
        print(f"       - {f}")

    docs = load_all_from_dir(data_dir)
    print(f"[INFO] {len(docs)} documento(s) carregado(s).")

    print("[INFO] Aplicando chunking...")
    chunks = classify_and_split(docs)
    print(f"[INFO] {len(chunks)} chunk(s) gerado(s).")

    print("[INFO] Gerando embeddings e indexando no Supabase pgvector...")
    vectorstore = create_vectorstore(chunks)

    if vectorstore is None:
        print("[INFO] Todos os documentos ja estavam indexados. Nada a fazer.")
        return

    print(f"[OK] Indexacao concluida! {len(chunks)} documento(s) enviados ao Supabase.")


if __name__ == "__main__":
    main()

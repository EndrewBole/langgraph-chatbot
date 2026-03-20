-- ============================================================
-- Temporalis AI — Supabase Setup Script
-- Execute no SQL Editor do Supabase Dashboard
-- ============================================================

-- 1. Habilitar extensão pgvector
create extension if not exists vector;

-- ============================================================
-- 2. Tabela de documentos (RAG vector store)
-- ============================================================
create extension if not exists "uuid-ossp";

create table if not exists public.documents (
  id uuid primary key default uuid_generate_v4(),
  content text not null,
  metadata jsonb default '{}',
  embedding vector(1536) not null
);

-- Índice HNSW para busca vetorial rápida (cosine distance)
create index if not exists documents_embedding_idx
  on public.documents
  using hnsw (embedding vector_cosine_ops)
  with (m = 16, ef_construction = 64);

-- Índice GIN para filtros em metadata (ex: content_hash, source)
create index if not exists documents_metadata_idx
  on public.documents
  using gin (metadata);

-- ============================================================
-- 3. Função RPC match_documents (usada pelo SupabaseVectorStore)
-- ============================================================
create or replace function public.match_documents(
  query_embedding vector(1536),
  match_count int default 10,
  filter jsonb default '{}'
) returns table (
  id uuid,
  content text,
  metadata jsonb,
  similarity float
) language plpgsql as $$
begin
  return query
  select
    documents.id,
    documents.content,
    documents.metadata,
    1 - (documents.embedding <=> query_embedding) as similarity
  from public.documents
  where case
    when filter != '{}' then documents.metadata @> filter
    else true
  end
  order by documents.embedding <=> query_embedding
  limit match_count;
end;
$$;

-- ============================================================
-- 4. Row Level Security (RLS)
-- ============================================================
alter table public.documents enable row level security;

-- Service role (backend) tem acesso total
create policy "Service role full access"
  on public.documents
  for all
  using (auth.role() = 'service_role')
  with check (auth.role() = 'service_role');

-- Anon/authenticated só pode ler (se precisar no futuro)
create policy "Read only for authenticated"
  on public.documents
  for select
  using (auth.role() = 'authenticated');

-- ============================================================
-- 5. Revogar acesso direto da anon key à tabela
-- ============================================================
revoke all on public.documents from anon;
grant select on public.documents to authenticated;
grant all on public.documents to service_role;

-- ============================================================
-- 6. Permissão para executar a função RPC
-- ============================================================
revoke execute on function public.match_documents from anon;
revoke execute on function public.match_documents from authenticated;
grant execute on function public.match_documents to service_role;

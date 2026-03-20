-- ============================================================
-- Temporalis AI — LangGraph Checkpointer (PostgreSQL)
-- Memória de conversas persistente via Supabase PostgreSQL
-- Execute no SQL Editor do Supabase Dashboard
-- ============================================================

-- 1. Tabela de controle de migrações
CREATE TABLE IF NOT EXISTS public.checkpoint_migrations (
    v INTEGER PRIMARY KEY
);

-- 2. Tabela de checkpoints (estado do grafo por thread/conversa)
CREATE TABLE IF NOT EXISTS public.checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    type TEXT,
    checkpoint JSONB NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

-- 3. Tabela de blobs (dados serializados dos channels do grafo)
CREATE TABLE IF NOT EXISTS public.checkpoint_blobs (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL,
    version TEXT NOT NULL,
    type TEXT NOT NULL,
    blob BYTEA,
    PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
);

-- 4. Tabela de writes (escritas pendentes entre nodes)
CREATE TABLE IF NOT EXISTS public.checkpoint_writes (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    type TEXT,
    blob BYTEA NOT NULL,
    task_path TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);

-- ============================================================
-- 5. Índices para performance (busca por thread_id)
-- ============================================================
CREATE INDEX IF NOT EXISTS checkpoints_thread_id_idx
    ON public.checkpoints(thread_id);

CREATE INDEX IF NOT EXISTS checkpoint_blobs_thread_id_idx
    ON public.checkpoint_blobs(thread_id);

CREATE INDEX IF NOT EXISTS checkpoint_writes_thread_id_idx
    ON public.checkpoint_writes(thread_id);

-- ============================================================
-- 6. Registrar migrações como aplicadas (v0 a v9)
-- ============================================================
INSERT INTO public.checkpoint_migrations (v)
VALUES (0),(1),(2),(3),(4),(5),(6),(7),(8),(9)
ON CONFLICT (v) DO NOTHING;

-- ============================================================
-- 7. Row Level Security (RLS)
-- ============================================================

-- checkpoints
ALTER TABLE public.checkpoints ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access on checkpoints"
    ON public.checkpoints FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- checkpoint_blobs
ALTER TABLE public.checkpoint_blobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access on checkpoint_blobs"
    ON public.checkpoint_blobs FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- checkpoint_writes
ALTER TABLE public.checkpoint_writes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access on checkpoint_writes"
    ON public.checkpoint_writes FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- checkpoint_migrations
ALTER TABLE public.checkpoint_migrations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access on checkpoint_migrations"
    ON public.checkpoint_migrations FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- ============================================================
-- 8. Revogar acesso de anon/authenticated
-- ============================================================
REVOKE ALL ON public.checkpoints FROM anon, authenticated;
REVOKE ALL ON public.checkpoint_blobs FROM anon, authenticated;
REVOKE ALL ON public.checkpoint_writes FROM anon, authenticated;
REVOKE ALL ON public.checkpoint_migrations FROM anon, authenticated;

GRANT ALL ON public.checkpoints TO service_role;
GRANT ALL ON public.checkpoint_blobs TO service_role;
GRANT ALL ON public.checkpoint_writes TO service_role;
GRANT ALL ON public.checkpoint_migrations TO service_role;

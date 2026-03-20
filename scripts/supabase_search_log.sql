-- Search analytics table
CREATE TABLE IF NOT EXISTS search_log (
    id BIGSERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    result_count INT NOT NULL DEFAULT 0,
    session_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for analytics queries
CREATE INDEX IF NOT EXISTS idx_search_log_created_at ON search_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_search_log_query ON search_log USING gin(to_tsvector('portuguese', query));

-- Useful analytics queries:

-- Top 10 queries with zero results (stock gap analysis)
-- SELECT query, COUNT(*) as searches
-- FROM search_log WHERE result_count = 0
-- GROUP BY query ORDER BY searches DESC LIMIT 10;

-- Top 10 most searched queries
-- SELECT query, COUNT(*) as searches, AVG(result_count) as avg_results
-- FROM search_log
-- GROUP BY query ORDER BY searches DESC LIMIT 10;

-- Daily search volume
-- SELECT DATE(created_at) as day, COUNT(*) as searches
-- FROM search_log GROUP BY day ORDER BY day DESC LIMIT 30;

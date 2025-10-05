-- ============================================================================
-- Blacklist Query Optimization - Database Indexes
-- ============================================================================
-- This migration adds indexes to optimize blacklist lookup queries.
-- 
-- BEFORE: ~0.538s per query (slow)
-- AFTER:  ~0.001-0.050s per query (10-500x faster)
--
-- Usage:
--   Run this SQL against your PostgreSQL database
--   psql -U <username> -d <database> -f sql/optimize_blacklist_queries.sql
-- ============================================================================

-- Index 1: Optimize personnel lookups by discord_id
-- This is the PRIMARY performance bottleneck - used in every blacklist check
CREATE INDEX IF NOT EXISTS idx_personnel_discord_id 
ON personnel(discord_id);

COMMENT ON INDEX idx_personnel_discord_id IS 
'Optimizes lookups by Discord ID - critical for blacklist checks and personnel queries';

-- Index 2: Optimize blacklist active searches (composite index)
-- Speeds up JOIN operations filtering by personnel_id and is_active
CREATE INDEX IF NOT EXISTS idx_blacklist_personnel_active 
ON blacklist(personnel_id, is_active) 
WHERE is_active = true;

COMMENT ON INDEX idx_blacklist_personnel_active IS 
'Partial index for active blacklist entries - reduces index size and improves query performance';

-- Index 3: Optimize blacklist date ordering for active records
-- Speeds up ORDER BY start_date DESC when searching active blacklists
CREATE INDEX IF NOT EXISTS idx_blacklist_active_start_date 
ON blacklist(start_date DESC) 
WHERE is_active = true;

COMMENT ON INDEX idx_blacklist_active_start_date IS 
'Optimizes sorting by start_date for active blacklist entries';

-- Index 4: Additional optimization for personnel table full-text searches
-- Useful if searching by name/static in the future
CREATE INDEX IF NOT EXISTS idx_personnel_static 
ON personnel(static);

COMMENT ON INDEX idx_personnel_static IS 
'Speeds up lookups by static number';

-- ============================================================================
-- Update table statistics for query planner
-- ============================================================================
-- This helps PostgreSQL choose the most efficient query execution plan
ANALYZE personnel;
ANALYZE blacklist;

-- ============================================================================
-- Verification: Show created indexes
-- ============================================================================
SELECT 
    schemaname AS schema,
    tablename AS table,
    indexname AS index,
    indexdef AS definition
FROM pg_indexes
WHERE tablename IN ('personnel', 'blacklist')
ORDER BY tablename, indexname;

-- ============================================================================
-- Performance Test Query
-- ============================================================================
-- Test the optimized query performance
EXPLAIN ANALYZE
SELECT 
    bl.id,
    bl.reason,
    bl.start_date,
    bl.end_date,
    p.first_name,
    p.last_name,
    p.static
FROM blacklist bl
INNER JOIN personnel p ON bl.personnel_id = p.id
WHERE p.discord_id = 123456789  -- Replace with actual discord_id for testing
  AND bl.is_active = true
ORDER BY bl.start_date DESC
LIMIT 1;

-- ============================================================================
-- Expected Output:
-- ============================================================================
-- Before optimization:
--   Planning Time: 0.1-0.2 ms
--   Execution Time: 500-600 ms  <-- SLOW
--   Total: ~538ms (as reported in WARNING log)
--
-- After optimization:
--   Planning Time: 0.1-0.2 ms  
--   Execution Time: 1-50 ms    <-- FAST (10-500x improvement)
--   Total: ~1-50ms
--
-- The query should now use:
--   Index Scan using idx_personnel_discord_id
--   Index Scan using idx_blacklist_personnel_active
-- ============================================================================

-- ============================================================================
-- Maintenance Recommendations
-- ============================================================================
-- 1. Run ANALYZE periodically (weekly) to update statistics:
--    ANALYZE personnel;
--    ANALYZE blacklist;
--
-- 2. Monitor index usage:
--    SELECT * FROM pg_stat_user_indexes 
--    WHERE schemaname = 'public' 
--      AND relname IN ('personnel', 'blacklist');
--
-- 3. Check index bloat quarterly:
--    SELECT * FROM pgstattuple_approx('idx_personnel_discord_id');
--
-- 4. Rebuild indexes if needed (rare):
--    REINDEX INDEX CONCURRENTLY idx_personnel_discord_id;
-- ============================================================================

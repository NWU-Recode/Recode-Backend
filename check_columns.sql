-- Query to check actual table structures in Supabase
-- Run this in Supabase SQL Editor

-- Check user_elo columns
SELECT 
    table_name,
    column_name, 
    data_type, 
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_schema = 'public' 
AND table_name = 'user_elo'
ORDER BY ordinal_position;

-- Check user_badge columns
SELECT 
    table_name,
    column_name, 
    data_type, 
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_schema = 'public' 
AND table_name = 'user_badge'
ORDER BY ordinal_position;

-- Check elo_events columns
SELECT 
    table_name,
    column_name, 
    data_type, 
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_schema = 'public' 
AND table_name = 'elo_events'
ORDER BY ordinal_position;

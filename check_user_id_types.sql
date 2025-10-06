-- Quick check: What is the data type of user_id in user_elo?
SELECT 
    table_name,
    column_name, 
    data_type,
    udt_name
FROM information_schema.columns 
WHERE table_schema = 'public' 
AND table_name IN ('user_elo', 'user_badge', 'elo_events')
AND column_name LIKE '%user%'
ORDER BY table_name, ordinal_position;

-- Also check what data exists in user_elo
SELECT * FROM public.user_elo LIMIT 5;

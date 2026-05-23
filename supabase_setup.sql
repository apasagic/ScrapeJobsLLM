-- Supabase Setup for ScrapeJobsLLM

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create jobs table
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id TEXT NOT NULL,
    source TEXT NOT NULL,
    title TEXT,
    company TEXT,
    location TEXT,
    description TEXT,
    url TEXT,
    tags TEXT[],
    experience TEXT,
    seniority TEXT,
    skills TEXT,
    salary TEXT,
    job_fitness TEXT,
    comment TEXT,
    embedding vector(384),  -- For all-MiniLM-L6-v2 model
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(job_id, source)
);

-- Create index for vector similarity search
CREATE INDEX ON jobs USING ivfflat (embedding vector_cosine_ops);

-- Create RPC function for similarity search
CREATE OR REPLACE FUNCTION similar_jobs(query_embedding vector, top_k int DEFAULT 5)
RETURNS TABLE(
    job_id text,
    source text,
    title text,
    company text,
    location text,
    description text,
    url text,
    tags text[],
    experience text,
    seniority text,
    skills text,
    salary text,
    job_fitness text,
    comment text,
    similarity float
)
AS $$
SELECT
    job_id,
    source,
    title,
    company,
    location,
    description,
    url,
    tags,
    experience,
    seniority,
    skills,
    salary,
    job_fitness,
    comment,
    1 - (embedding <=> query_embedding) as similarity
FROM jobs
ORDER BY embedding <=> query_embedding
LIMIT top_k;
$$ LANGUAGE sql;

-- Optional: Create a view for analytics
CREATE VIEW job_analytics AS
SELECT
    source,
    COUNT(*) as job_count,
    AVG(array_length(tags, 1)) as avg_tags
FROM jobs
GROUP BY source;

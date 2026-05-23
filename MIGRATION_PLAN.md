# Cloud Migration and Dashboard Plan

## 1. Goal
Build a hosted ML job ingestion and analytics service with:
- job collection from multiple sources (JSearch, RemoteOK, etc.)
- deduplication by `job_id` + `source`
- vector search for user queries
- user profile / CV upload support
- analytics dashboard with dark theme and green accents

## 2. Recommended provider
### Use Supabase first
Supabase is the fastest path for an MVP because it provides:
- hosted Postgres database
- pgvector support for embeddings
- built-in auth for user email profiles
- serverless functions for API logic
- easy Python and JavaScript client libraries

### Reserve AWS for later if needed
Use AWS once you need:
- more complex scale and multi-tenant architecture
- advanced search engines (OpenSearch, Qdrant)
- custom compute (Lambda, ECS, App Runner)
- enterprise security and Secrets Manager

## 3. Service layer design
The service layer should isolate application logic from persistence details.

### Core responsibilities
- ingest jobs from any source
- normalize job metadata
- deduplicate jobs before insert
- store embeddings and metadata
- search job vectors
- provide analytics and counts
- manage user profiles and query history

### Key interfaces
- `StorageAdapter` (provider-agnostic)
- `ChromaStorageAdapter` for local development
- `SupabaseStorageAdapter` or `AWSStorageAdapter` for cloud migration
- `JobService` for ingestion, search, and CRUD operations
- `AnalyticsService` for reporting and dashboard metrics

## 4. Migration steps
### Phase 1: local service layer ✅ COMPLETED
- finalize `service/` modules with `StorageAdapter` abstraction
- implement `ChromaStorageAdapter` for local development
- implement `SupabaseStorageAdapter` for cloud migration
- update `main.py` to use configurable storage adapter
- add dashboard script for data exploration
- CLI input for user queries and database clearing

### Phase 2: Supabase backend 🚧 IN PROGRESS
- create Supabase project at https://supabase.com
- enable Postgres with `pgvector` extension
- run `supabase_setup.sql` in Supabase SQL editor to create tables and functions
- update `config.yaml` with:
  - `storage.adapter: "supabase"`
  - `storage.supabase_url: "your-project-url"`
  - `storage.supabase_key: "your-anon-key"`
- test migration by running `python main.py` with Supabase adapter
- migrate existing job data from local Chroma if needed

### Phase 3: API and auth
- build a service API layer with endpoints:
  - `POST /ingest`
  - `POST /search`
  - `GET /jobs`
  - `GET /stats`
  - `POST /users`
- use Supabase Auth for email login
- use env variables for secrets

### Phase 4: dashboard
- connect the dashboard to the service API
- display:
  - total jobs, sources, and locations
  - ML area distribution
  - top skills and libraries
  - experience buckets
  - vector search results

### Phase 5: scheduling and automation
- add a periodic ingestion job
- refresh remote sources every few days
- keep the cloud database current without duplicate inserts

## 5. Data model suggestions
### `jobs` table
- `job_id` TEXT PRIMARY KEY
- `source` TEXT
- `title` TEXT
- `description` TEXT
- `link` TEXT
- `location` TEXT
- `salary` TEXT
- `tags` TEXT
- `skills` TEXT
- `experience` TEXT
- `seniority` TEXT
- `job_fitness` TEXT
- `comment` TEXT
- `created_at` TIMESTAMP
- `updated_at` TIMESTAMP
- `embedding` VECTOR

### `users` table
- `id` UUID
- `email` TEXT
- `name` TEXT
- `created_at` TIMESTAMP
- `updated_at` TIMESTAMP

### `user_queries` table
- `id` UUID
- `user_id` UUID
- `query_text` TEXT
- `created_at` TIMESTAMP

## 6. Running the dashboard locally
1. Install dependencies:
   ```bash
   pip install streamlit plotly pandas
   ```
2. Run:
   ```bash
   streamlit run dashboard.py
   ```
3. The page will show local job analytics if jobs are loaded into the vector store.

## 7. Next steps
- implement a Supabase storage adapter
- add user auth and CV upload endpoints
- migrate analytics to the cloud with stored SQL views
- create a polished React dashboard if desired

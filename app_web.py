"""
Flask web application for Job Search with CV Upload
"""
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # Suppress TensorFlow logging
os.environ['PROTOBUF_PYTHON_MESSAGE_FACTORY_NO_COPY'] = 'true'

import warnings
warnings.filterwarnings('ignore')

# Suppress warnings from import
import sys
from io import StringIO

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

# Capture stderr during imports
old_stderr = sys.stderr
sys.stderr = StringIO()

try:
    from flask import Flask, render_template, request, jsonify, send_file
    import yaml
    import json
    import shutil
    from datetime import datetime
    from io import BytesIO
    from pathlib import Path
    import traceback

    from service.job_service import JobService
    from service.storage_adapter import ChromaStorageAdapter, SupabaseStorageAdapter
    from service.analytics_service import AnalyticsService
    import scraper
    import http.client
    from utilities import summarize_job_search_results, generate_html_report, extract_chroma_entry, sort_jobs_by_fitness
finally:
    sys.stderr = old_stderr

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Global storage adapter (initialized on first request)
storage = None
analytics = None
config = None
last_storage_recovery = None


def load_config():
    with open("config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def make_openrouter_client(config):
    openrouter_key = os.environ.get("OPENROUTER_KEY") or config.get("api", {}).get("openrouter_key")
    if not openrouter_key:
        return None

    import httpx
    import openai

    return openai.OpenAI(
        api_key=openrouter_key,
        base_url=config.get("api", {}).get("openrouter_url", "https://openrouter.ai/api/v1"),
        http_client=httpx.Client(trust_env=False),
    )


def make_scraper(config, cv_text):
    api_config = config.get("api", {})
    rapidapi_key = os.environ.get("RAPIDAPI_KEY") or api_config.get("rapidapi_key") or "test-key-for-testing"
    rapidapi_host = api_config.get("rapidapi_host", "jsearch.p.rapidapi.com")
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": rapidapi_host,
        "Content-Type": "application/json",
    }
    conn = http.client.HTTPSConnection(rapidapi_host)
    return scraper.JobScraper(config=config, conn=conn, headers=headers, my_cv=cv_text)


def initialize_chroma_storage(path):
    """Create a Chroma adapter and convert native panics into normal Python errors."""
    try:
        from chromadb.api.shared_system_client import SharedSystemClient

        SharedSystemClient.clear_system_cache()
        return ChromaStorageAdapter(path=path)
    except BaseException as exc:
        if exc.__class__.__name__ in {"KeyboardInterrupt", "SystemExit"}:
            raise
        try:
            from chromadb.api.shared_system_client import SharedSystemClient

            SharedSystemClient.clear_system_cache()
        except Exception:
            pass
        raise RuntimeError(
            f"Could not open Chroma database at {path!r}. "
            "The persistent store may be locked, readonly, or incompatible with this Chroma version."
        ) from exc


def reset_chroma_store(cfg, reason=""):
    """Archive the current Chroma store so Chroma can create a clean database."""
    global storage, analytics, last_storage_recovery

    storage = None
    analytics = None

    storage_config = cfg.get("storage", {})
    chroma_path = Path(storage_config.get("chroma_path", "chroma_db/"))
    archive_path = None
    if chroma_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_path = chroma_path.with_name(f"{chroma_path.name}_archived_{timestamp}")
        shutil.move(str(chroma_path), str(archive_path))

    chroma_path.mkdir(parents=True, exist_ok=True)
    try:
        from chromadb.api.shared_system_client import SharedSystemClient

        SharedSystemClient.clear_system_cache()
    except Exception:
        pass

    last_storage_recovery = {
        "archived_path": str(archive_path) if archive_path else None,
        "reason": reason,
    }
    return last_storage_recovery


def ingest_from_sources(query, cv_text, clear=False):
    cfg = load_config()
    recovery = None
    try:
        init_storage()
    except RuntimeError as exc:
        if not clear or cfg.get("storage", {}).get("adapter", "chroma") != "chroma":
            raise

        recovery = reset_chroma_store(cfg, reason=str(exc))
        init_storage()

    job_scraper = make_scraper(cfg, cv_text)
    source_counts = {}
    errors = []
    all_jobs = []

    for source_name, scraper_name in (("JSearch", "JSearch"), ("RemoteOK", "remoteok")):
        try:
            jobs, _ = job_scraper.scrape_job(scraper_name, query=query)
            source_counts[source_name] = len(jobs)
            all_jobs.extend(jobs)
        except Exception as exc:
            source_counts[source_name] = 0
            errors.append(f"{source_name}: {exc}")

    service = JobService(storage)
    ingested_jobs = service.ingest_jobs(all_jobs, source="web_search", clear=clear)

    return {
        "scraper": job_scraper,
        "jobs": all_jobs,
        "ingested_jobs": ingested_jobs,
        "source_counts": source_counts,
        "errors": errors,
        "storage_recovery": recovery,
    }


def search_saved_jobs(query, cv_text="", num_jobs=10, client=None):
    init_storage()
    service = JobService(storage)
    search_top_k = max(num_jobs * 4, 25)
    search_results = service.search_jobs(query, top_k=search_top_k)
    matched_jobs = sort_jobs_by_fitness(extract_chroma_entry(search_results))
    shown_jobs = matched_jobs[:num_jobs]
    summary = summarize_job_search_results(shown_jobs, query, cv_text, client)

    return {
        "matched_jobs": shown_jobs,
        "summary": summary,
        "candidate_count": len(matched_jobs),
    }

def init_storage():
    """Initialize storage adapter based on config"""
    global storage, analytics, config
    
    if storage is not None:
        print(f"⚠️  Storage already initialized: {type(storage).__name__}")
        return storage
    
    try:
        # Load config
        config = load_config()
        
        storage_config = config.get("storage", {})
        adapter_type = storage_config.get("adapter", "chroma")
        print(f"🔧 Config loaded, adapter_type: {adapter_type}", file=sys.stderr)
        
        try:
            if adapter_type == "supabase":
                print("Initializing Supabase adapter...")
                storage = SupabaseStorageAdapter(
                    url=storage_config.get("supabase_url"),
                    key=storage_config.get("supabase_key")
                )
                print("✅ Supabase adapter initialized")
            else:
                print("Initializing ChromaDB adapter...")
                storage = initialize_chroma_storage(storage_config.get("chroma_path", "chroma_db/"))
                print("✅ ChromaDB adapter initialized")
        except Exception as e:
            if adapter_type == "chroma":
                raise
            print(f"❌ Error initializing {adapter_type}: {e}")
            print("⚠️  Falling back to ChromaDB...")
            storage = initialize_chroma_storage(storage_config.get("chroma_path", "chroma_db/"))
        
        analytics = AnalyticsService(storage)
        return storage
    except Exception as e:
        print(f"❌ Critical error initializing storage: {e}")
        raise

@app.route('/')
def index():
    """Main page"""
    return render_template('search.html')


@app.route('/api/ingest', methods=['POST'])
def ingest_jobs():
    """Fetch jobs from all configured sources, compare/enrich against CV, and store them."""
    try:
        data = request.json or {}
        query = data.get("query", "").strip()
        cv_text = data.get("cv", "").strip()
        clear = bool(data.get("clear", False))

        if not query:
            return jsonify({"error": "Search query is required"}), 400
        if not cv_text:
            return jsonify({"error": "CV text is required"}), 400

        result = ingest_from_sources(query, cv_text, clear=clear)
        total_jobs = storage.count_jobs()

        return jsonify({
            "success": True,
            "query": query,
            "scraped_count": len(result["jobs"]),
            "ingested_count": len(result["ingested_jobs"]),
            "source_counts": result["source_counts"],
            "errors": result["errors"],
            "storage_recovery": result["storage_recovery"],
            "total_jobs_in_db": total_jobs,
            "llm_enabled": result["scraper"].client is not None,
        })
    except Exception as e:
        print(f"Error during ingestion: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e), "details": traceback.format_exc()}), 500


@app.route('/api/search-db', methods=['POST'])
def search_database():
    """Search jobs already stored in the database without scraping new jobs."""
    try:
        data = request.json or {}
        query = data.get("query", "").strip()
        cv_text = data.get("cv", "").strip()
        num_jobs = max(1, min(int(data.get("num_jobs", 10)), 50))

        if not query:
            return jsonify({"error": "Search query is required"}), 400

        cfg = load_config()
        client = make_openrouter_client(cfg)
        search_result = search_saved_jobs(query, cv_text=cv_text, num_jobs=num_jobs, client=client)

        return jsonify({
            "success": True,
            "query": query,
            "matched_jobs": search_result["matched_jobs"],
            "summary": search_result["summary"],
            "llm_enabled": client is not None,
            "stats": {
                "total_jobs_in_db": storage.count_jobs(),
                "matched_count": len(search_result["matched_jobs"]),
                "candidate_count": search_result["candidate_count"],
            },
        })
    except Exception as e:
        print(f"Error during database search: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e), "details": traceback.format_exc()}), 500

@app.route('/api/search', methods=['POST'])
def search_jobs():
    """API endpoint for job search with CV"""
    try:
        init_storage()
        
        data = request.json
        query = data.get('query', '').strip()
        cv_text = data.get('cv', '').strip()
        num_jobs = max(1, min(int(data.get('num_jobs', 10)), 50))
        
        if not query:
            return jsonify({'error': 'Search query is required'}), 400
        
        if not cv_text:
            return jsonify({'error': 'CV text is required'}), 400
        
        print(f"\n🔍 Searching for: {query}")
        print(f"📄 CV length: {len(cv_text)} characters")
        
        # Get config
        with open("config.yaml") as f:
            config = yaml.safe_load(f)
        
        # Setup scraper (with test key)
        rapidapi_key = os.environ.get("RAPIDAPI_KEY") or config.get("api", {}).get("rapidapi_key") or "test-key-for-testing"
        headers = {
            'x-rapidapi-key': rapidapi_key,
            'x-rapidapi-host': config.get("api", {}).get("rapidapi_host", "jsearch.p.rapidapi.com"),
            'Content-Type': "application/json"
        }
        
        conn = http.client.HTTPSConnection(config.get("api", {}).get("rapidapi_host", "jsearch.p.rapidapi.com"))
        
        # Initialize scraper
        job_scraper = scraper.JobScraper(
            config=config,
            conn=conn,
            headers=headers,
            my_cv=cv_text
        )
        
        print("🔄 Scraping jobs from configured sources...")
        jobs_jsearch, _ = job_scraper.scrape_job("JSearch", query=query)
        jobs_remoteok, _ = job_scraper.scrape_job("remoteok", query=query)
        all_jobs = jobs_remoteok + jobs_jsearch
        
        print(f"✅ Scraped {len(all_jobs)} total jobs")
        
        # Ingest jobs into database
        print("💾 Ingesting jobs into database...")
        job_service = JobService(storage)
        job_service.ingest_jobs(all_jobs, source="web_search", clear=False)
        
        print(f"✅ Jobs ingested. Total in DB: {storage.count_jobs()}")
        
        # Search for matching jobs
        print(f"🔎 Searching for matches...")
        search_top_k = max(num_jobs * 3, 20)
        search_results = job_service.search_jobs(query, top_k=search_top_k)
        matched_jobs = extract_chroma_entry(search_results)
        matched_jobs = sort_jobs_by_fitness(matched_jobs)
        shown_jobs = matched_jobs[:num_jobs]
        
        print(f"✅ Found {len(matched_jobs)} matching jobs")
        
        # Generate summary
        summary = summarize_job_search_results(shown_jobs, query, cv_text, job_scraper.client)
        
        # Get analytics
        total_jobs = storage.count_jobs()
        area_dist = analytics.get_area_distribution()
        top_skills = analytics.get_top_skills(limit=10)
        top_libs = analytics.get_top_libraries(limit=10)
        
        result = {
            'success': True,
            'query': query,
            'matched_jobs': shown_jobs,
            'summary': summary,
            'llm_enabled': job_scraper.client is not None,
            'stats': {
                'total_jobs_in_db': total_jobs,
                'matched_count': len(shown_jobs),
                'candidate_count': len(matched_jobs),
                'top_areas': dict(list(area_dist.items())[:5]),
                'top_skills': top_skills[:5],
                'top_libraries': top_libs[:5]
            }
        }
        
        print("✅ Search completed successfully!")
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ Error during search: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e), 'details': traceback.format_exc()}), 500

@app.route('/api/jobs', methods=['GET'])
def get_jobs():
    """Get all jobs from database"""
    try:
        init_storage()
        
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        jobs = storage.get_jobs(limit=limit, offset=offset)
        total = storage.count_jobs()
        
        return jsonify({
            'jobs': jobs,
            'total': total,
            'limit': limit,
            'offset': offset
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get dashboard statistics"""
    try:
        init_storage()
        return jsonify(analytics.get_dashboard_stats(limit=15))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/clear', methods=['POST'])
def clear_database():
    """Clear all jobs from database"""
    try:
        init_storage()
        storage.clear()
        return jsonify({'success': True, 'message': 'Database cleared'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/export', methods=['POST'])
def export_results():
    """Export search results to HTML"""
    try:
        data = request.json
        matched_jobs = data.get('jobs', [])
        summary = data.get('summary', '')
        
        html_report = generate_html_report(matched_jobs, summary)
        
        # Create BytesIO object
        html_bytes = BytesIO(html_report.encode('utf-8'))
        
        return send_file(
            html_bytes,
            mimetype='text/html',
            as_attachment=True,
            download_name=f"job_search_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("\n" + "="*60)
    print("Starting Job Search Web Application")
    print("="*60)
    try:
        print("📍 Access at: http://localhost:5000")
        print("="*60 + "\n")
        print("About to call app.run()...")
        port = int(os.environ.get("WEB_PORT", "5000"))
        app.run(debug=False, host="127.0.0.1", port=port, use_reloader=False, threaded=True)
    except Exception as e:
        print(f"❌ Error starting Flask: {e}")
        import traceback
        traceback.print_exc()

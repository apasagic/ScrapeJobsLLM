import http.client
import os
import sys

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import re
import time
import openai
import yaml
import json
import tiktoken
import scraper
from utilities import summarize_job_search_results, scrape_job_remoteok, generate_html_report, send_email, extract_chroma_entry
from service.job_service import JobService
from service.storage_adapter import ChromaStorageAdapter, SupabaseStorageAdapter

#from llama_cpp import Llama
from email.message import EmailMessage

def process_text(user_input, clear_chroma_db=None):

    
    # Load configuration
    with open("config.yaml") as f:
        config = yaml.safe_load(f)
    
    if clear_chroma_db is None:
        clear_chroma_db = config.get("settings", {}).get("clear_chroma_db", True)
    
    # Your CV to match job fitness
    with open("cv.txt", "r", encoding="utf-8") as f:
        my_cv = f.read()
    
    rapidapi_key = os.environ.get("RAPIDAPI_KEY") or config.get("api", {}).get("rapidapi_key")
    rapidapi_host = config.get("api", {}).get("rapidapi_host", "jsearch.p.rapidapi.com")
    if not rapidapi_key:
        raise ValueError("RapidAPI key is not set. Set RAPIDAPI_KEY environment variable or api.rapidapi_key in config.yaml")

    headers = {
       'x-rapidapi-key': rapidapi_key,
       'x-rapidapi-host': rapidapi_host,
       'Content-Type': "application/json"
    }

    conn = http.client.HTTPSConnection(rapidapi_host)
    
    user_email = os.environ.get("NOTIFY_EMAIL") or config.get("email", {}).get("notify_to")
    if not user_email:
        raise ValueError("Notification email is not set. Set NOTIFY_EMAIL environment variable or email.notify_to in config.yaml")
    
    job_scraper  = scraper.JobScraper(config = config, conn=conn, headers=headers, my_cv=my_cv)
    
    # Scrape jobs from both sources
    jobs_remoteok, _ = job_scraper.scrape_job("remoteok")
    jobs_jsearch, jobs_query_text = job_scraper.scrape_job("JSearch")
    jobs = jobs_remoteok + jobs_jsearch
    
    # Extract the job rows
    #job_html_snippet = "\n".join(str(card) for card in job_cards[:36])  # 20 jobs max
    
    search_query = user_input.strip() if user_input else "machine learning remote"

    storage_config = config.get("storage", {})
    adapter_type = storage_config.get("adapter", "chroma")
    
    if adapter_type == "chroma":
        storage = ChromaStorageAdapter(path=storage_config.get("chroma_path", "chroma_db/"))
    elif adapter_type == "supabase":
        storage = SupabaseStorageAdapter(
            url=storage_config.get("supabase_url"),
            key=storage_config.get("supabase_key")
        )
    else:
        raise ValueError(f"Unknown storage adapter: {adapter_type}")
    
    job_service = JobService(storage)
    job_service.ingest_jobs(jobs, clear=clear_chroma_db)

    search_results = job_service.search_jobs(search_query, top_k=10)
    matched_jobs = extract_chroma_entry(search_results)

    summary_text = summarize_job_search_results(matched_jobs, search_query, my_cv, job_scraper.client)

    html_report = generate_html_report(matched_jobs, summary_text)
    
    with open("jobs.html", "w", encoding="utf-8") as f:
        f.write(html_report)
    
    print("✅ jobs.html created with a beautiful table!")
    
    # Display dashboard summary
    print("\n" + "="*50)
    print("📊 DASHBOARD SUMMARY")
    print("="*50)
    
    from service.analytics_service import AnalyticsService
    analytics = AnalyticsService(storage)
    
    total_jobs = storage.count_jobs()
    print(f"📈 Total Jobs in Database: {total_jobs}")
    
    if total_jobs > 0:
        area_dist = analytics.get_area_distribution()
        print(f"🌍 Top Areas: {dict(list(area_dist.items())[:5])}")
        
        top_skills = analytics.get_top_skills(limit=5)
        print(f"🛠️  Top Skills: {top_skills}")
        
        top_libs = analytics.get_top_libraries(limit=5)
        print(f"📚 Top Libraries: {top_libs}")
    
    print(f"🔍 Search Query: '{search_query}'")
    print(f"🎯 Found {len(matched_jobs)} matching jobs")
    
    print(f"\n📄 Summary: {summary_text[:200]}...")
    
    print(f"\n📁 Results exported to: jobs.html")
    print("="*50)
    
    # Skip email for testing
    # send_email(user_email, "Your Job Report", html_report)
    print("📧 Email sending skipped for testing")
    
    
    #print(vector_db.query_similar("Electric vehicle battery management system"))
    #print(vector_db.query_similar("Time series forecasting"))

if __name__ == "__main__":
    # Example usage
    user_input = input("Enter your job search query (e.g., 'machine learning engineer'): ").strip()
    if not user_input:
        user_input = "machine learning remote"
    
    clear_db_input = input("Clear existing database? (y/n, default n): ").strip().lower()
    clear_chroma_db = clear_db_input == 'y'
    
    process_text(user_input, clear_chroma_db=clear_chroma_db)

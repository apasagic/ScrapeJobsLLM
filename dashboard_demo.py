#!/usr/bin/env python3
"""
Simple test script to demonstrate dashboard functionality
"""
import yaml
from service.job_service import JobService
from service.storage_adapter import ChromaStorageAdapter
from service.analytics_service import AnalyticsService

def main():
    print("🚀 Starting Dashboard Demo...")

    try:
        # Load config
        with open("config.yaml") as f:
            config = yaml.safe_load(f)
        print("✅ Config loaded")

        # Initialize storage and services
        storage_config = config.get("storage", {})
        storage = ChromaStorageAdapter(path=storage_config.get("chroma_path", "chroma_db/"))
        job_service = JobService(storage)
        analytics = AnalyticsService(storage)
        print("✅ Services initialized")

        print("\n" + "="*60)
        print("📊 DASHBOARD DEMO")
        print("="*60)

        # Get basic stats
        total_jobs = storage.count_jobs()
        print(f"📈 Total Jobs in Database: {total_jobs}")

        if total_jobs > 0:
            # Get analytics data
            area_dist = analytics.get_area_distribution()
            print(f"🌍 Top Areas: {dict(list(area_dist.items())[:5])}")

            top_skills = analytics.get_top_skills(limit=5)
            print(f"🛠️  Top Skills: {top_skills}")

            top_libs = analytics.get_top_libraries(limit=5)
            print(f"📚 Top Libraries: {top_libs}")

            # Get some sample jobs
            sample_jobs = storage.get_jobs(limit=3)
            print(f"\n📋 Sample Jobs:")
            for i, job in enumerate(sample_jobs, 1):
                print(f"  {i}. {job.get('title', 'N/A')} at {job.get('company', 'N/A')} ({job.get('location', 'N/A')})")

            print(f"\n✅ Dashboard data loaded successfully!")
            print(f"💾 Storage: ChromaDB ({total_jobs} jobs)")
        else:
            print("📭 No jobs in database. Run main.py first to scrape and store jobs.")

        print("="*60)

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
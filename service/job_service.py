from typing import TYPE_CHECKING, Any, Dict, List, Optional

from utilities import remove_duplicates

if TYPE_CHECKING:
    from .storage_adapter import StorageAdapter


class JobService:
    def __init__(self, storage_adapter: "StorageAdapter"):
        self.storage = storage_adapter

    @staticmethod
    def normalize_job(job: Dict[str, Any], source: Optional[str] = None) -> Dict[str, Any]:
        # A batch source should be a fallback label, not a replacement for the
        # scraper/API source already present on the job.
        source = job.get("source") or source or "unknown"
        tags_value = job.get("tags", "")
        if isinstance(tags_value, list):
            tags = [str(item).strip() for item in tags_value if item]
        else:
            tags = [tag.strip() for tag in str(tags_value).split(",") if tag.strip()]

        return {
            "id": str(job.get("id", "N/A")),
            "source": source,
            "title": job.get("title", "N/A"),
            "company": job.get("company", "N/A"),
            "location": job.get("location", "Remote"),
            "url": job.get("url", job.get("link", "N/A")),
            "description": job.get("description", "N/A"),
            "experience": job.get("experience", "N/A"),
            "seniority": job.get("seniority", "N/A"),
            "skills": job.get("skills", "N/A"),
            "tags": ", ".join(tags) if tags else "N/A",
            "salary": job.get("salary", "N/A"),
            "job_fitness": job.get("job_fitness", "N/A"),
            "comment": job.get("comment", "N/A"),
        }

    def ingest_jobs(self, jobs: List[Dict[str, Any]], source: Optional[str] = None, clear: bool = False) -> List[Dict[str, Any]]:
        normalized = [self.normalize_job(job, source=source) for job in jobs]
        unique_jobs = remove_duplicates(normalized)
        if clear:
            return self.storage.add_jobs(unique_jobs, clear=True)
        return self.storage.add_unique_jobs(unique_jobs)

    def search_jobs(self, query_text: str, top_k: int = 10) -> Dict[str, Any]:
        return self.storage.query_jobs(query_text, top_k=top_k)

    def list_jobs(self, limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
        return self.storage.get_jobs(limit=limit, offset=offset)

    def job_count(self) -> int:
        return self.storage.count_jobs()

    def count_by_field(self, field: str, limit: Optional[int] = None) -> Dict[str, int]:
        return self.storage.count_by_metadata(field, limit=limit)

    def delete_jobs(self, ids: Optional[List[str]] = None, where: Optional[Dict[str, Any]] = None, where_document: Optional[Dict[str, Any]] = None) -> None:
        self.storage.delete_jobs(ids=ids, where=where, where_document=where_document)

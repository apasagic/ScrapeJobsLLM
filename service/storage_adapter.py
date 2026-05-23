from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import os


def split_tags(value: Any) -> List[str]:
    if not value or value == "N/A":
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


class StorageAdapter(ABC):
    @abstractmethod
    def count_jobs(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def get_jobs(self, limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def add_jobs(self, jobs: List[Dict[str, Any]], clear: bool = False) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def add_unique_jobs(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def query_jobs(self, query_text: str, top_k: int = 5, include: Optional[List[str]] = None) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def delete_jobs(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def count_by_metadata(self, field: str, limit: Optional[int] = None) -> Dict[str, int]:
        raise NotImplementedError


class ChromaStorageAdapter(StorageAdapter):
    def __init__(self, path: str = "chroma_db/", collection_name: str = "jobs"):
        from chroma_db import ChromaDB

        self.db = ChromaDB(path=path, collection_name=collection_name)

    def count_jobs(self) -> int:
        return self.db.count()

    def get_jobs(self, limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
        result = self.db.get_all(limit=limit, offset=offset)
        return result.get("metadatas", []) if result else []

    def add_jobs(self, jobs: List[Dict[str, Any]], clear: bool = False) -> List[Dict[str, Any]]:
        if clear:
            self.db.clear_collection()
        self.db.add_to_vector_db(jobs)
        return jobs

    def add_unique_jobs(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self.db.add_unique_jobs(jobs)

    def query_jobs(self, query_text: str, top_k: int = 5, include: Optional[List[str]] = None) -> Dict[str, Any]:
        return self.db.query_similar(query_text, top_k=top_k, include=include)

    def delete_jobs(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.db.delete_jobs(ids=ids, where=where, where_document=where_document)

    def clear(self) -> None:
        self.db.clear_collection()

    def count_by_metadata(self, field: str, limit: Optional[int] = None) -> Dict[str, int]:
        return self.db.count_by_metadata(field, limit=limit)


class SupabaseStorageAdapter(StorageAdapter):
    def __init__(self, url: str = None, key: str = None, table_name: str = "jobs"):
        from supabase import create_client

        self.url = url or os.getenv("SUPABASE_URL")
        self.key = key or os.getenv("SUPABASE_ANON_KEY")
        if not self.url or not self.key:
            raise ValueError("Supabase URL and key must be provided via env vars or params")
        self.supabase = create_client(self.url, self.key)
        self.table_name = table_name
        self.model = None  # Lazy load

    def _generate_embedding(self, text: str) -> List[float]:
        if self.model is None:
            from sentence_transformers import SentenceTransformer
            try:
                self.model = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
            except TypeError:
                self.model = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception:
                self.model = SentenceTransformer("all-MiniLM-L6-v2")
        return self.model.encode(text).tolist()

    def count_jobs(self) -> int:
        result = self.supabase.table(self.table_name).select("*", count="exact").execute()
        return result.count

    def get_jobs(self, limit: Optional[int] = None, offset: int = 0) -> List[Dict[str, Any]]:
        query = self.supabase.table(self.table_name).select("*").range(offset, offset + (limit or 1000) - 1)
        result = query.execute()
        jobs = []
        for row in result.data:
            job = {
                "id": row.get("job_id", row.get("id", "N/A")),
                "source": row.get("source", "supabase"),
                "title": row.get("title", "N/A"),
                "company": row.get("company", "N/A"),
                "location": row.get("location", "Remote"),
                "description": row.get("description", "N/A"),
                "url": row.get("url", row.get("link", "N/A")),
                "tags": row.get("tags", []),
                "experience": row.get("experience", "N/A"),
                "seniority": row.get("seniority", "N/A"),
                "skills": row.get("skills", "N/A"),
                "salary": row.get("salary", "N/A"),
                "job_fitness": row.get("job_fitness", "N/A"),
                "comment": row.get("comment", "N/A"),
            }
            jobs.append(job)
        return jobs

    def add_jobs(self, jobs: List[Dict[str, Any]], clear: bool = False) -> List[Dict[str, Any]]:
        if clear:
            self.clear()
        # Generate embeddings and prepare data
        data = []
        for job in jobs:
            embedding = self._generate_embedding(job.get("description", ""))
            data.append({
                "job_id": job.get("id", "N/A"),
                "source": job.get("source", "unknown"),
                "title": job.get("title", "N/A"),
                "company": job.get("company", "N/A"),
                "location": job.get("location", "Remote"),
                "description": job.get("description", "N/A"),
                "url": job.get("url", job.get("link", "N/A")),
                "tags": split_tags(job.get("tags", [])),
                "experience": job.get("experience", "N/A"),
                "seniority": job.get("seniority", "N/A"),
                "skills": job.get("skills", "N/A"),
                "salary": job.get("salary", "N/A"),
                "job_fitness": job.get("job_fitness", "N/A"),
                "comment": job.get("comment", "N/A"),
                "embedding": embedding,
            })
        # Insert with upsert to handle duplicates
        self.supabase.table(self.table_name).upsert(data, on_conflict="job_id,source").execute()
        return jobs

    def add_unique_jobs(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Check existing
        existing_keys = set()
        result = self.supabase.table(self.table_name).select("job_id,source").execute()
        for row in result.data:
            existing_keys.add((row["job_id"], row["source"]))
        
        new_jobs = []
        for job in jobs:
            key = (job.get("id", "N/A"), job.get("source", "unknown"))
            if key not in existing_keys:
                new_jobs.append(job)
        
        if new_jobs:
            self.add_jobs(new_jobs)
        return new_jobs

    def query_jobs(self, query_text: str, top_k: int = 5, include: Optional[List[str]] = None) -> Dict[str, Any]:
        query_embedding = self._generate_embedding(query_text)
        # Use pgvector similarity search
        result = self.supabase.rpc("similar_jobs", {
            "query_embedding": query_embedding,
            "top_k": top_k
        }).execute()
        
        matched_jobs = []
        for row in result.data:
            job = {
                "id": row.get("job_id", row.get("id", "N/A")),
                "source": row.get("source", "supabase"),
                "title": row.get("title", "N/A"),
                "company": row.get("company", "N/A"),
                "location": row.get("location", "Remote"),
                "description": row.get("description", "N/A"),
                "url": row.get("url", row.get("link", "N/A")),
                "tags": row.get("tags", []),
                "experience": row.get("experience", "N/A"),
                "seniority": row.get("seniority", "N/A"),
                "skills": row.get("skills", "N/A"),
                "salary": row.get("salary", "N/A"),
                "job_fitness": row.get("job_fitness", "N/A"),
                "comment": row.get("comment", "N/A"),
                "similarity": row.get("similarity", 0),
            }
            matched_jobs.append(job)
        
        return {
            "ids": [[job["id"] for job in matched_jobs]],
            "metadatas": [matched_jobs],
            "documents": [[job.get("description", "") for job in matched_jobs]],
            "distances": [[1 - float(job.get("similarity", 0)) for job in matched_jobs]],
        }

    def delete_jobs(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
    ) -> None:
        query = self.supabase.table(self.table_name).delete()
        if ids:
            query = query.in_("job_id", ids)
        if where:
            for key, value in where.items():
                query = query.eq(key, value)
        query.execute()

    def clear(self) -> None:
        self.supabase.table(self.table_name).delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()

    def count_by_metadata(self, field: str, limit: Optional[int] = None) -> Dict[str, int]:
        # This might need a custom RPC or aggregation
        # For simplicity, fetch all and count
        result = self.supabase.table(self.table_name).select(field).execute()
        counts = {}
        for row in result.data:
            value = row.get(field)
            if value:
                counts[value] = counts.get(value, 0) + 1
        # Sort and limit
        sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        if limit:
            sorted_counts = sorted_counts[:limit]
        return dict(sorted_counts)

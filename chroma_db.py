def vector_id_for_job(job):
    source = str(job.get("source", "unknown")).strip() or "unknown"
    job_id = str(job.get("id", "unknown")).strip() or "unknown"
    return f"{source}:{job_id}"

class ChromaDB:
    """
    This class handles the connection to the ChromaDB vector database.
    It allows adding job descriptions, deduplication, deletion, basic stats, and similarity search.
    """
    def __init__(self, path="chroma_db/", collection_name="jobs", model_name="all-MiniLM-L6-v2"):
        import chromadb
        from chromadb.api.shared_system_client import SharedSystemClient
        from sentence_transformers import SentenceTransformer

        self.path = path
        self.collection_name = collection_name
        SharedSystemClient.clear_system_cache()
        self.client = chromadb.PersistentClient(path=self.path)
        self.collection = self.client.get_or_create_collection(self.collection_name)
        try:
            self.model = SentenceTransformer(model_name, local_files_only=True)
        except TypeError:
            self.model = SentenceTransformer(model_name)
        except Exception:
            self.model = SentenceTransformer(model_name)

    def count(self):
        return self.collection.count()

    def peek(self, limit=10):
        return self.collection.peek(limit=limit)

    def get_all(self, limit=None, offset=0):
        limit = limit if limit is not None else self.count()
        return self.collection.get(limit=limit, offset=offset)

    def delete_jobs(self, ids=None, where=None, where_document=None):
        self.collection.delete(ids=ids, where=where, where_document=where_document)

    def clear_collection(self):
        """Remove all existing job data from the persistent Chroma collection."""
        existing = self.collection.get(include=[])
        ids = existing.get("ids", [])
        if ids:
            self.collection.delete(ids=ids)

    def _existing_job_keys(self):
        result = self.get_all(limit=self.count())
        existing = set()
        for metadata in result.get("metadatas", []):
            if not metadata:
                continue
            existing.add((metadata.get("id"), metadata.get("source")))
        return existing

    def filter_new_jobs(self, jobs):
        existing = self._existing_job_keys()
        unique_jobs = []
        seen = set()

        for job in jobs:
            key = (job.get("id"), job.get("source"))
            if key in seen:
                continue
            seen.add(key)
            if key not in existing:
                unique_jobs.append(job)

        return unique_jobs

    def add_to_vector_db(self, jobs, skip_duplicates=False):
        if skip_duplicates:
            jobs = self.filter_new_jobs(jobs)

        if not jobs:
            return []

        docs = [job.get("description", "") for job in jobs]
        ids = [vector_id_for_job(job) for job in jobs]
        embeddings = self.model.encode(docs).tolist()

        self.collection.add(
            documents=docs,
            embeddings=embeddings,
            metadatas=jobs,
            ids=ids
        )

        return jobs

    def add_unique_jobs(self, jobs):
        return self.add_to_vector_db(jobs, skip_duplicates=True)

    def query_similar(self, query_text, top_k=5, include=None):
        query_embedding = self.model.encode([query_text])[0].tolist()
        include = include or ["metadatas", "documents", "distances"]
        return self.collection.query(query_embeddings=[query_embedding], n_results=top_k, include=include)

    def count_by_metadata(self, field, limit=None):
        result = self.get_all(limit=limit)
        counts = {}
        for metadata in result.get("metadatas", []):
            if not metadata:
                continue
            value = metadata.get(field, "Unknown")
            counts[value] = counts.get(value, 0) + 1
        return counts

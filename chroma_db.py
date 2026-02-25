import chromadb
from sentence_transformers import SentenceTransformer

class ChromaDB:
    """
    This class handles the connection to the ChromaDB vector database.
    It allows adding job descriptions and querying similar jobs based on a CV.
    """
    def __init__(self):
      self.client = chromadb.PersistentClient(path="chroma_db/")
      self.collection = self.client.get_or_create_collection("jobs")
      self.model = SentenceTransformer("all-MiniLM-L6-v2")  # or similar

    def add_to_vector_db(self, jobs):
      docs = [job['description'] for job in jobs]
      ids = [job['id'] for job in jobs]
      embeddings = self.model.encode(docs).tolist()
    
      self.collection.add(
        documents=docs,
        embeddings=embeddings,
        metadatas=jobs,
        ids=ids
      )

    def query_similar(self,cv_text, top_k=5):
      cv_embedding = self.model.encode([cv_text])[0].tolist()
      return self.collection.query(query_embeddings=[cv_embedding], n_results=top_k)

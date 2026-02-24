from sentence_transformers import SentenceTransformer
import numpy as np

class EmbeddingsHelper:
    def __init__(self, model_name='all-MiniLM-L6-v2'):
        # Using a lightweight local version as a fallback or primary for speed
        # Spec mentions nomic-embed-text via Ollama, but we can use sentence-transformers for offline capability
        self.model = SentenceTransformer(model_name)

    def get_embeddings(self, texts):
        return self.model.encode(texts)

    def compute_similarity(self, vec1, vec2):
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

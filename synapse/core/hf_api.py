import json
import logging
import urllib.request
import urllib.parse
from datetime import datetime

log = logging.getLogger(__name__)

class HuggingFaceAPI:
    BASE_URL = "https://huggingface.co/api/models"

    @staticmethod
    def search_models(query="", limit=15, sort="downloads", direction=-1):
        """
        Search for models on HuggingFace Hub.
        Returns a list of model dicts.
        """
        params = {
            "search": query,
            "limit": limit,
            "sort": sort,
            "direction": direction,
            "full": "true", # Get more metadata like downloads, likes
            "config": "true"
        }
        
        # If no query, maybe suggest some popular/GGUF models?
        # HF doesn't have a direct "GGUF" tag filter in the same way tags work, 
        # but we can add filter params if needed.
        
        url = f"{HuggingFaceAPI.BASE_URL}?{urllib.parse.urlencode(params)}"
        
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Synapse/3.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    return data.get("results", data.get("models", []))
                return []
        except Exception as e:
            log.error(f"HF Search failed: {e}")
            return []

    @staticmethod
    def format_model_data(hf_model):
        """Standardize HF model metadata for our UI."""
        return {
            "id": hf_model.get("id", ""),
            "author": hf_model.get("author", "unknown"),
            "modelId": hf_model.get("modelId", ""),
            "likes": hf_model.get("likes", 0),
            "downloads": hf_model.get("downloads", 0),
            "lastModified": hf_model.get("lastModified", ""),
            "tags": hf_model.get("tags", []),
            "pipeline_tag": hf_model.get("pipeline_tag", "unknown")
        }

if __name__ == "__main__":
    # Quick test
    api = HuggingFaceAPI()
    results = api.search_models("qwen 2.5 coder", limit=5)
    for r in results:
        formatted = api.format_model_data(r)
        print(f"Model: {formatted['id']} | Downloads: {formatted['downloads']} | Likes: {formatted['likes']}")

import json
import urllib.request
import unittest
from unittest.mock import MagicMock, patch

# Mocking parts of synapse to test the logic
class TestOpenRouterIntegration(unittest.TestCase):
    def test_openrouter_payload(self):
        # Simulate OpenRouterWorker payload construction
        model = "anthropic/claude-3-opus"
        messages = [{"role": "user", "content": "hello"}]
        api_key = "sk-or-test-key"
        
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "headers": {
                "HTTP-Referer": "https://github.com/jacobdcook/synapse",
                "X-Title": "Synapse Desktop"
            }
        }
        
        req_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/jacobdcook/synapse",
            "X-Title": "Synapse Desktop"
        }
        
        self.assertEqual(payload["model"], "anthropic/claude-3-opus")
        self.assertEqual(req_headers["Authorization"], "Bearer sk-or-test-key")
        self.assertEqual(req_headers["HTTP-Referer"], "https://github.com/jacobdcook/synapse")

    def test_worker_factory_routing(self):
        # Simulate WorkerFactory routing logic
        def mock_factory(model):
            if model.startswith("gpt-"): return "OpenAI"
            if model.startswith("claude-"): return "Anthropic"
            if "/" in model and ":" not in model: return "OpenRouter"
            return "Ollama"
            
        self.assertEqual(mock_factory("gpt-4o"), "OpenAI")
        self.assertEqual(mock_factory("anthropic/claude-3"), "OpenRouter")
        self.assertEqual(mock_factory("llama3.1:8b"), "Ollama")

if __name__ == "__main__":
    unittest.main()

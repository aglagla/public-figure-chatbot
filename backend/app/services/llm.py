
"""LLM client using the OpenAI Python SDK against any OpenAI-compatible server.

Set:
- LLM_BASE_URL (e.g., http://localhost:8001/v1 for vLLM)
- LLM_API_KEY (string required by SDK; can be dummy for local servers)
- LLM_MODEL (e.g., gpt-oss, llama-3.1-8b-instruct, mistral)
"""
from typing import List, Dict, Any
from openai import OpenAI

class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model

    def chat(self, messages: List[Dict[str, str]], max_tokens: int = 512, temperature: float = 0.6) -> Dict[str, Any]:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        choice = resp.choices[0]
        return {
            "content": choice.message.content,
            "usage": getattr(resp, "usage", None),
            "model": resp.model,
        }

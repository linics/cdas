"""DeepSeek/SiliconFlow 集成的通用工具。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Callable, List, Sequence, TypeVar

import requests

from pydantic import BaseModel

from app.config import Settings, get_settings


T = TypeVar("T", bound=BaseModel)


class EmbeddingProvider:
    """包装 SiliconFlow Embedding，未配置时回退到哈希向量。"""

    def __init__(self, settings: Settings, dim: int | None = None) -> None:
        self.settings = settings
        self.dim = dim or self._infer_default_dim(settings.siliconflow_embedding_model)

    @staticmethod
    def _infer_default_dim(model_name: str) -> int:
        lowered = (model_name or "").lower()
        if "bge-large" in lowered:
            return 1024
        if "bge-base" in lowered:
            return 768
        if "bge-small" in lowered:
            return 384
        if "bge" in lowered and "m3" in lowered:
            return 1024
        return 1024

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        if not texts:
            return []
        if self.settings.siliconflow_api_key:
            try:
                vectors = self._embed_with_siliconflow(texts)
                dim = len(vectors[0]) if vectors and vectors[0] else 0
                _log_ai_error(
                    "embedding_request",
                    f"ok model={self.settings.siliconflow_embedding_model} count={len(texts)} dim={dim}",
                )
                return vectors
            except Exception as exc:  # pragma: no cover - 外部 API 失败回退
                detail = str(exc)
                if isinstance(exc, requests.HTTPError) and exc.response is not None:
                    detail = f"status={exc.response.status_code} body={exc.response.text[:400]}"
                _log_ai_error("embedding_request", detail)
                _log_ai_error("embedding_fallback", "hash_fallback_due_to_embedding_error")
                return self._fallback_embeddings(texts)
        _log_ai_error("embedding_fallback", "hash_fallback_no_api_key")
        return self._fallback_embeddings(texts)

    def _embed_with_siliconflow(self, texts: Sequence[str]) -> List[List[float]]:
        response = requests.post(
            "https://api.siliconflow.cn/v1/embeddings",
            headers={
                "Authorization": f"Bearer {self.settings.siliconflow_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.settings.siliconflow_embedding_model,
                "input": list(texts),
            },
            timeout=60,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data", [])
        embeddings = [item.get("embedding", []) for item in data]
        if len(embeddings) != len(texts):
            raise RuntimeError("SiliconFlow embeddings size mismatch")
        if embeddings:
            vector_dim = len(embeddings[0])
            if vector_dim <= 0:
                raise RuntimeError("SiliconFlow returned empty embedding vector")
            if any(len(vector) != vector_dim for vector in embeddings):
                raise RuntimeError("SiliconFlow returned inconsistent embedding dimensions")
            self.dim = vector_dim
        return embeddings

    def _fallback_embeddings(self, texts: Sequence[str]) -> List[List[float]]:
        embeddings: List[List[float]] = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).digest()
            vector: List[float] = []
            while len(vector) < self.dim:
                for byte in digest:
                    vector.append((byte - 128) / 128.0)
                    if len(vector) >= self.dim:
                        break
            embeddings.append(vector)
        return embeddings


class RerankProvider:
    """调用 SiliconFlow Rerank；未配置时直接返回原顺序。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def rerank(self, query: str, documents: Sequence[str]) -> List[int]:
        if not documents:
            return []
        if not self.settings.siliconflow_api_key:
            return list(range(len(documents)))

        # 控制上下文长度，避免 SiliconFlow Rerank 触发 8k token 上限。
        max_docs = 6
        max_doc_chars = 600
        index_map: List[int] = []
        prepared_documents: List[str] = []
        for idx, doc in enumerate(documents):
            if len(prepared_documents) >= max_docs:
                break
            text = str(doc or "").strip()
            if not text:
                continue
            prepared_documents.append(text[:max_doc_chars])
            index_map.append(idx)
        if not prepared_documents:
            return list(range(len(documents)))

        try:
            response = requests.post(
                "https://api.siliconflow.cn/v1/rerank",
                headers={
                    "Authorization": f"Bearer {self.settings.siliconflow_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.settings.siliconflow_rerank_model,
                    "query": query,
                    "documents": prepared_documents,
                },
                timeout=60,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # pragma: no cover - 外部 API 失败回退
            detail = str(exc)
            if isinstance(exc, requests.HTTPError) and exc.response is not None:
                detail = f"status={exc.response.status_code} body={exc.response.text[:400]}"
            _log_ai_error("rerank_request", detail)
            return list(range(len(documents)))

        _log_ai_error(
            "rerank_request",
            f"ok model={self.settings.siliconflow_rerank_model} docs={len(prepared_documents)}",
        )

        data = payload.get("data", [])
        if not isinstance(data, list):
            return list(range(len(documents)))

        scored: List[tuple[int, float]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            index_raw = item.get("index")
            score = item.get("relevance_score", item.get("score", 0))
            if index_raw is None:
                continue
            index_text = str(index_raw).strip()
            if not index_text:
                continue
            try:
                index = int(float(index_text))
            except Exception:
                continue
            try:
                score = float(score)
            except Exception:
                score = 0.0
            scored.append((index, score))

        if not scored:
            return list(range(len(documents)))

        scored.sort(key=lambda pair: pair[1], reverse=True)
        indices = [idx for idx, _ in scored if 0 <= idx < len(documents)]
        if index_map:
            indices = [index_map[idx] for idx in indices if 0 <= idx < len(index_map)]
        if not indices:
            return list(range(len(documents)))
        return indices


class DeepSeekJSONClient:
    """使用 DeepSeek Chat Completions 生成结构化 JSON。"""

    def __init__(
        self,
        settings: Settings,
        temperature: float = 0.2,
        max_output_tokens: int = 2048,
        request_timeout: int = 60,
    ) -> None:
        self.settings = settings
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.request_timeout = request_timeout

    @property
    def is_available(self) -> bool:
        return bool(self.settings.deepseek_api_key)

    def structured_predict(
        self,
        schema: type[T],
        system_prompt: str,
        user_prompt: str,
        normalize: Callable[[dict], dict] | None = None,
    ) -> T:
        if not self.settings.deepseek_api_key:
            raise RuntimeError("DeepSeek API 未配置")
        response = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.settings.deepseek_api_key}",
            },
            json={
                "model": self.settings.deepseek_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": f"{user_prompt}\n\n只输出 JSON，不要额外解释。",
                    },
                ],
                "temperature": self.temperature,
                "stream": False,
                "max_tokens": self.max_output_tokens,
                "response_format": {"type": "json_object"},
            },
            timeout=self.request_timeout,
        )
        response.raise_for_status()
        payload = response.json()
        content = (
            payload.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        data = _extract_json(content)
        if normalize:
            data = normalize(data)
        return schema.model_validate(data)

    def predict_json(self, system_prompt: str, user_prompt: str) -> dict:
        if not self.settings.deepseek_api_key:
            raise RuntimeError("DeepSeek API 未配置")
        try:
            response = requests.post(
                "https://api.deepseek.com/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.settings.deepseek_api_key}",
                },
                json={
                    "model": self.settings.deepseek_model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user",
                            "content": f"{user_prompt}\n\n只输出JSON，不要额外解释。",
                        },
                    ],
                    "temperature": self.temperature,
                    "stream": False,
                    "max_tokens": self.max_output_tokens,
                    "response_format": {"type": "json_object"},
                },
                timeout=self.request_timeout,
            )
            response.raise_for_status()
        except Exception as exc:
            _log_ai_error("deepseek_request", str(exc))
            raise
        payload = response.json()
        content = (
            payload.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        _log_ai_error("deepseek_content", "ok", content)
        try:
            return _extract_json(content)
        except Exception as exc:
            _log_ai_error("deepseek_parse", str(exc), content)
            raise


def _extract_json(text: str) -> dict:
    """从模型输出中提取 JSON 对象。"""
    text = _cleanup_json_text(text)
    if text.startswith("{") and text.endswith("}"):
        return json.loads(text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("未找到 JSON 输出")
    return json.loads(text[start : end + 1])


def _cleanup_json_text(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\\s*", "", text)
        text = re.sub(r"\\s*```$", "", text)
    text = text.strip()
    text = re.sub(r",\\s*([}\\]])", r"\\1", text)
    return text


def _log_ai_error(stage: str, message: str, content: str | None = None) -> None:
    try:
        snippet = ""
        if content:
            snippet = content[:2000]
        log_path = _ai_debug_log_path()
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{stage}] {message}\n")
            if snippet:
                handle.write(f"{snippet}\n")
            handle.write("---\n")
    except Exception:
        pass


def _ai_debug_log_path() -> Path:
    settings = get_settings()
    settings.ai_logs_dir.mkdir(parents=True, exist_ok=True)
    return settings.ai_logs_dir / "ai_debug.log"

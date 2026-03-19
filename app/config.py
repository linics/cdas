"""应用配置管理。

使用 Pydantic Settings 统一读取环境变量，便于在本地/生产之间切换。
"""

from functools import lru_cache
import os
from pathlib import Path
import re
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """核心配置项。

    - ``database_url``：默认使用本地 SQLite，便于快速启动。
    - ``chroma_persist_dir``：向量库持久化目录，后续步骤会用到。
    - ``deepseek_api_key``：DeepSeek API Key，用于结构化生成。
    - ``siliconflow_api_key``：SiliconFlow API Key，用于 Embedding。
    """

    database_url: str = Field(
        default="sqlite:///./storage/cdas.db", description="SQLAlchemy 数据库 URL"
    )
    documents_dir: Path = Field(
        default=Path("./storage/documents"), description="上传文件存储目录"
    )
    chroma_persist_dir: Path = Field(
        default=Path("./storage/chroma"), description="Chroma 持久化目录"
    )
    deepseek_api_key: Optional[str] = Field(
        default=None, description="DeepSeek API Key，用于对话/结构化生成"
    )
    deepseek_model: str = Field(
        default="deepseek-chat", description="DeepSeek 对话模型 ID"
    )
    siliconflow_api_key: Optional[str] = Field(
        default=None, description="SiliconFlow API Key，用于 Embedding"
    )
    siliconflow_embedding_model: str = Field(
        default="BAAI/bge-large-zh-v1.5", description="SiliconFlow Embedding 模型 ID"
    )
    siliconflow_rerank_model: str = Field(
        default="BAAI/bge-reranker-v2-m3", description="SiliconFlow Rerank 模型 ID"
    )
    auth_secret_key: str = Field(
        default="", description="认证签名密钥，生产环境必须配置"
    )
    auth_token_expire_hours: int = Field(
        default=24, ge=1, le=168, description="认证 Token 过期时间（小时）"
    )
    ai_logs_dir: Path = Field(default=Path("./storage"), description="运行日志目录")
    cors_allowed_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        description="允许跨域来源，逗号分隔",
    )
    cors_allow_origin_regex: Optional[str] = Field(
        default=r"^http://(localhost|127\.0\.0\.1):\d+$",
        description="允许跨域来源正则（可空）",
    )

    model_config = {
        "env_prefix": "CDAS_",
        "env_file": str(BASE_DIR / ".env"),
        "env_file_encoding": "utf-8",
    }

    @property
    def cors_origins_list(self) -> list[str]:
        return [item.strip() for item in self.cors_allowed_origins.split(",") if item.strip()]

    @model_validator(mode="after")
    def normalize_paths(self) -> "Settings":
        self.documents_dir = _resolve_path(self.documents_dir)
        self.chroma_persist_dir = _resolve_path(self.chroma_persist_dir)
        self.ai_logs_dir = _resolve_path(self.ai_logs_dir)

        self.auth_secret_key = self.auth_secret_key.strip()
        if not self.auth_secret_key:
            raise ValueError("CDAS_AUTH_SECRET_KEY is required")

        if self.database_url.startswith("sqlite:///"):
            db_target = self.database_url[len("sqlite:///") :]
            if db_target and db_target != ":memory:":
                if _looks_like_windows_abs_path(db_target) and os.name != "nt":
                    db_target = "./storage/cdas.db"
                db_path = Path(db_target)
                if not db_path.is_absolute():
                    absolute = (BASE_DIR / db_path).resolve()
                    self.database_url = f"sqlite:///{absolute.as_posix()}"

        return self


def _resolve_path(path_value: Path) -> Path:
    raw = str(path_value)
    if _looks_like_windows_abs_path(raw) and os.name != "nt":
        tail = raw.split(":", 1)[-1].lstrip("/\\")
        path_value = Path("./storage") / tail
    return path_value if path_value.is_absolute() else (BASE_DIR / path_value).resolve()


def _looks_like_windows_abs_path(value: str) -> bool:
    return bool(re.match(r"^[A-Za-z]:[\\/]", value or ""))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """缓存后的全局配置实例。"""

    return Settings()

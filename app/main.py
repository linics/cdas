"""FastAPI 入口 - CDAS 跨学科作业系统。"""

from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.api.documents import router as documents_router
from app.api.v2 import router as v2_router
from app.config import get_settings
from app.db import Base, engine
from app.migrations import run_migrations


def create_app() -> FastAPI:
    """应用工厂，便于后续测试与拓展路由。"""

    logger = logging.getLogger("cdas.api")
    settings = get_settings()

    def init_models() -> None:
        """启动时确保表存在并初始化学科数据。"""
        from app.models import (
            Assignment,
            ClassGroup,
            ClassGroupMember,
            ClassMember,
            Classroom,
            Document,
            Evaluation,
            PRESET_SUBJECTS,
            ProjectGroup,
            Subject,
            Submission,
            User,
        )

        try:
            # 优先使用迁移脚本管理结构演进。
            run_migrations(engine)
        except OperationalError as exc:
            # 兼容首次启动场景（旧迁移脚本基于既有表做 ALTER）。
            if "no such table" not in str(exc).lower():
                raise
            Base.metadata.create_all(bind=engine)
            run_migrations(engine)
        else:
            # 兜底保证模型中新增但尚未迁移覆盖的表被创建。
            Base.metadata.create_all(bind=engine)
        try:
            log_path: Path = settings.ai_logs_dir / "ai_status.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(
                    f"deepseek_api_key_set={bool(settings.deepseek_api_key)}\n"
                )
        except Exception:
            pass

        from app.db import SessionLocal

        db = SessionLocal()
        try:
            existing = db.query(Subject).first()
            if not existing:
                for data in PRESET_SUBJECTS:
                    subject = Subject(**data)
                    db.add(subject)
                db.commit()
                print("[CDAS] 学科数据已自动初始化")
        finally:
            db.close()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        init_models()
        yield

    app = FastAPI(
        title="CDAS API",
        version="2.0.0",
        description="跨学科作业系统 API",
        lifespan=lifespan,
    )

    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_origin_regex=settings.cors_allow_origin_regex or None,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )

    from fastapi import Request

    @app.middleware("http")
    async def catch_exceptions_middleware(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:
            logger.exception(
                "Unhandled exception",
                extra={
                    "path": str(request.url.path),
                    "method": request.method,
                },
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "服务器内部错误，请稍后重试"},
            )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # 旧版 API (保持兼容)
    app.include_router(documents_router, prefix="/api")
    
    # 新版 API v2
    app.include_router(v2_router)

    return app


app = create_app()

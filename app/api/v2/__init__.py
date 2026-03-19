"""API v2 路由包入口。"""

from fastapi import APIRouter

from app.api.v2 import auth, subjects, assignments, submissions, evaluations, classes

router = APIRouter(prefix="/api/v2")

# 注册子路由
router.include_router(auth.router, prefix="/auth", tags=["认证"])
router.include_router(subjects.router, prefix="/subjects", tags=["学科"])
router.include_router(assignments.router, prefix="/assignments", tags=["作业"])
router.include_router(submissions.router, prefix="/submissions", tags=["提交"])
router.include_router(evaluations.router, prefix="/evaluations", tags=["评价"])
router.include_router(classes.router, prefix="/classes", tags=["班级"])

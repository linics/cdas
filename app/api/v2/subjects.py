"""学科与核心素养API。"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Subject, PRESET_SUBJECTS

router = APIRouter()


# === Schemas ===

class CoreCompetency(BaseModel):
    dimension: str
    description: str


class SubjectResponse(BaseModel):
    id: int
    code: str
    name: str
    category: str
    primary_available: bool
    middle_available: bool
    grade_range: Optional[str]
    core_competencies: List[CoreCompetency]

    model_config = ConfigDict(from_attributes=True)


class SubjectListResponse(BaseModel):
    subjects: List[SubjectResponse]
    total: int


# === API 端点 ===

@router.get("/", response_model=SubjectListResponse)
async def list_subjects(
    stage: Optional[str] = None,  # "primary" / "middle"
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取学科列表，可按学段和类别筛选。"""
    query = db.query(Subject)
    
    if stage == "primary":
        query = query.filter(Subject.primary_available == True)
    elif stage == "middle":
        query = query.filter(Subject.middle_available == True)
    
    if category:
        query = query.filter(Subject.category == category)
    
    subjects = query.all()
    return {"subjects": subjects, "total": len(subjects)}


@router.get("/{subject_id}", response_model=SubjectResponse)
async def get_subject(subject_id: int, db: Session = Depends(get_db)):
    """获取单个学科详情。"""
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="学科不存在")
    return subject


@router.get("/code/{code}", response_model=SubjectResponse)
async def get_subject_by_code(code: str, db: Session = Depends(get_db)):
    """通过code获取学科。"""
    subject = db.query(Subject).filter(Subject.code == code).first()
    if not subject:
        raise HTTPException(status_code=404, detail="学科不存在")
    return subject


@router.post("/init")
async def init_subjects(db: Session = Depends(get_db)):
    """初始化预置学科数据（仅开发使用）。"""
    # 检查是否已初始化
    existing = db.query(Subject).first()
    if existing:
        return {"message": "学科数据已存在", "count": db.query(Subject).count()}
    
    # 插入预置数据
    for data in PRESET_SUBJECTS:
        subject = Subject(**data)
        db.add(subject)
    
    db.commit()
    return {"message": "学科数据初始化成功", "count": len(PRESET_SUBJECTS)}


@router.get("/categories/list")
async def list_categories():
    """获取学科类别列表。"""
    return {
        "categories": [
            {"code": "humanities", "name": "人文社科", "subjects": ["语文", "道德与法治", "历史", "地理", "英语"]},
            {"code": "science", "name": "自然科学", "subjects": ["科学", "物理", "化学", "生物学", "数学"]},
            {"code": "technology", "name": "技术类", "subjects": ["信息科技", "劳动"]},
            {"code": "arts", "name": "艺体类", "subjects": ["艺术", "体育与健康"]},
        ]
    }

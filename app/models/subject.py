"""学科模型定义 - 学科体系与核心素养。"""

from typing import Any, Dict, List, Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db import Base


class Subject(Base):
    """学科模型 - 基于义务教育课程方案（2022年版）。
    
    根据产品设计文档 2.1 节定义的学科列表。
    """
    
    __tablename__ = "subjects"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)  # "chinese", "math"
    name: Mapped[str] = mapped_column(String(50), nullable=False)  # "语文", "数学"
    category: Mapped[str] = mapped_column(String(30), nullable=False)  # "人文社科", "自然科学" 等
    
    # 学段适用性
    primary_available: Mapped[bool] = mapped_column(default=True)  # 小学可用
    middle_available: Mapped[bool] = mapped_column(default=True)  # 初中可用
    grade_range: Mapped[Optional[str]] = mapped_column(String(50))  # 如 "3-9" 表示3年级起
    
    # 核心素养 (JSON格式)
    # 格式: [{"dimension": "文化自信", "description": "对中华优秀传统文化的认同"}]
    core_competencies: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    
    # 跨学科概念关联
    cross_disciplinary_concepts: Mapped[List[str]] = mapped_column(JSON, default=list)
    
    def __repr__(self) -> str:
        return f"<Subject(id={self.id}, code={self.code}, name={self.name})>"


# 预置学科数据（用于初始化）
PRESET_SUBJECTS = [
    {
        "code": "chinese",
        "name": "语文",
        "category": "人文社科",
        "primary_available": True,
        "middle_available": True,
        "core_competencies": [
            {"dimension": "文化自信", "description": "对中华优秀传统文化的认同"},
            {"dimension": "语言运用", "description": "语言文字运用能力"},
            {"dimension": "思维能力", "description": "思维发展与品质提升"},
            {"dimension": "审美创造", "description": "审美能力和审美品位"},
        ]
    },
    {
        "code": "math",
        "name": "数学",
        "category": "自然科学",
        "primary_available": True,
        "middle_available": True,
        "core_competencies": [
            {"dimension": "数感/抽象能力", "description": "数感、量感、符号意识"},
            {"dimension": "运算能力", "description": "运算能力"},
            {"dimension": "几何直观", "description": "几何直观、空间观念"},
            {"dimension": "推理意识/能力", "description": "推理意识"},
            {"dimension": "数据意识/观念", "description": "数据意识"},
            {"dimension": "模型意识/观念", "description": "模型意识"},
            {"dimension": "应用意识", "description": "应用意识"},
            {"dimension": "创新意识", "description": "创新意识"},
        ]
    },
    {
        "code": "english",
        "name": "英语",
        "category": "人文社科",
        "primary_available": True,
        "middle_available": True,
        "grade_range": "3-9",
        "core_competencies": [
            {"dimension": "语言能力", "description": "核心素养的基础要素"},
            {"dimension": "文化意识", "description": "核心素养的价值取向"},
            {"dimension": "思维品质", "description": "核心素养的心智特征"},
            {"dimension": "学习能力", "description": "核心素养的发展条件"},
        ]
    },
    {
        "code": "politics",
        "name": "道德与法治",
        "category": "人文社科",
        "primary_available": True,
        "middle_available": True,
        "core_competencies": [
            {"dimension": "政治认同", "description": "社会主义建设者和接班人必须具备的思想前提"},
            {"dimension": "道德修养", "description": "立身成人之本"},
            {"dimension": "法治观念", "description": "行为的指引"},
            {"dimension": "健全人格", "description": "包括沟通交流能力等"},
            {"dimension": "责任意识", "description": "社会责任感"},
        ]
    },
    {
        "code": "history",
        "name": "历史",
        "category": "人文社科",
        "primary_available": False,
        "middle_available": True,
        "grade_range": "7-9",
        "core_competencies": [
            {"dimension": "唯物史观", "description": "历史唯物主义的基本观点"},
            {"dimension": "时空观念", "description": "在特定时空条件下认识事物"},
            {"dimension": "史料实证", "description": "通过史料了解历史"},
            {"dimension": "历史解释", "description": "对历史事物进行理性分析"},
            {"dimension": "家国情怀", "description": "对祖国和民族的认同与热爱"},
        ]
    },
    {
        "code": "geography",
        "name": "地理",
        "category": "人文社科",
        "primary_available": False,
        "middle_available": True,
        "grade_range": "7-8",
        "core_competencies": [
            {"dimension": "人地协调观", "description": "地理课程内容蕴含的最核心价值观"},
            {"dimension": "综合思维", "description": "认识地理事物的思维方式"},
            {"dimension": "区域认知", "description": "认识区域的思维方式"},
            {"dimension": "地理实践力", "description": "行动能力和品质"},
        ]
    },
    {
        "code": "science",
        "name": "科学",
        "category": "自然科学",
        "primary_available": True,
        "middle_available": False,
        "grade_range": "1-6",
        "core_competencies": [
            {"dimension": "科学观念", "description": "对客观事物的认识"},
            {"dimension": "科学思维", "description": "思维方法和能力"},
            {"dimension": "探究实践", "description": "科学探究和跨学科实践能力"},
            {"dimension": "态度责任", "description": "对待科学的情意和责任感"},
        ]
    },
    {
        "code": "physics",
        "name": "物理",
        "category": "自然科学",
        "primary_available": False,
        "middle_available": True,
        "grade_range": "8-9",
        "core_competencies": [
            {"dimension": "物理观念", "description": "从物理学视角形成的认识"},
            {"dimension": "科学思维", "description": "科学推理和论证"},
            {"dimension": "科学探究", "description": "探究能力"},
            {"dimension": "科学态度与责任", "description": "科学精神和社会责任"},
        ]
    },
    {
        "code": "chemistry",
        "name": "化学",
        "category": "自然科学",
        "primary_available": False,
        "middle_available": True,
        "grade_range": "9",
        "core_competencies": [
            {"dimension": "化学观念", "description": "元素观、变化观、能量观等"},
            {"dimension": "科学思维", "description": "证据推理、模型建构等"},
            {"dimension": "科学探究与实践", "description": "实验探究和跨学科实践"},
            {"dimension": "科学态度与责任", "description": "科学精神和社会责任感"},
        ]
    },
    {
        "code": "biology",
        "name": "生物学",
        "category": "自然科学",
        "primary_available": False,
        "middle_available": True,
        "grade_range": "7-8",
        "core_competencies": [
            {"dimension": "生命观念", "description": "对生命本质的认识"},
            {"dimension": "科学思维", "description": "科学推理和论证"},
            {"dimension": "探究实践", "description": "科学探究和跨学科实践"},
            {"dimension": "态度责任", "description": "对待科学和社会的态度"},
        ]
    },
    {
        "code": "it",
        "name": "信息科技",
        "category": "技术类",
        "primary_available": True,
        "middle_available": True,
        "core_competencies": [
            {"dimension": "信息意识", "description": "对信息敏感性和价值判断"},
            {"dimension": "计算思维", "description": "问题分解和算法思维"},
            {"dimension": "数字化学习与创新", "description": "利用数字工具学习和创造"},
            {"dimension": "信息社会责任", "description": "信息安全和伦理意识"},
        ]
    },
    {
        "code": "pe",
        "name": "体育与健康",
        "category": "艺体类",
        "primary_available": True,
        "middle_available": True,
        "core_competencies": [
            {"dimension": "运动能力", "description": "体能和运动技能"},
            {"dimension": "健康行为", "description": "健康的生活方式"},
            {"dimension": "体育品德", "description": "体育精神和品格"},
        ]
    },
    {
        "code": "art",
        "name": "艺术",
        "category": "艺体类",
        "primary_available": True,
        "middle_available": True,
        "core_competencies": [
            {"dimension": "审美感知", "description": "对美的感知和体验"},
            {"dimension": "艺术表现", "description": "艺术表达和创作"},
            {"dimension": "创意实践", "description": "创造性艺术实践"},
            {"dimension": "文化理解", "description": "对艺术文化的理解"},
        ]
    },
    {
        "code": "labor",
        "name": "劳动",
        "category": "技术类",
        "primary_available": True,
        "middle_available": True,
        "core_competencies": [
            {"dimension": "劳动观念", "description": "正确的劳动价值观"},
            {"dimension": "劳动能力", "description": "劳动知识和技能"},
            {"dimension": "劳动习惯与品质", "description": "劳动态度和品格"},
            {"dimension": "劳动精神", "description": "劳模精神、工匠精神"},
        ]
    },
]

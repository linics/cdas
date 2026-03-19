"""Assignment generation prompt builders."""

from dataclasses import dataclass

from app.prompts.template_loader import load_template


@dataclass(frozen=True)
class AssignmentPreviewPromptContext:
    title: str
    topic: str
    description: str
    school_stage: str
    grade: int
    assignment_type: str
    subtype: str
    main_subject: str
    related_subjects: str
    reference_document: str
    type_guidance: str
    subtype_guidance: str
    inquiry_depth: str
    submission_mode: str
    duration_weeks: int
    depth_guidance: str
    template_json: str
    rag_context: str


@dataclass(frozen=True)
class LessonPlanPromptContext:
    title: str
    topic: str
    school_stage: str
    grade: int
    assignment_type: str
    inquiry_depth: str
    submission_mode: str
    duration_weeks: int
    main_subject: str
    related_subjects: str
    lesson_plan_excerpt: str
    template_json: str
    rag_context: str


def build_assignment_preview_prompt(ctx: AssignmentPreviewPromptContext) -> tuple[str, str]:
    rag_section = ""
    if ctx.rag_context:
        rag_section = f"\nSubject-specific context (reference only):\n{ctx.rag_context}\n"

    system_prompt = load_template("assignment_preview.system.txt")
    user_prompt = load_template("assignment_preview.user.txt").format(
        title=ctx.title,
        topic=ctx.topic,
        description=ctx.description or "none",
        school_stage=ctx.school_stage,
        grade=ctx.grade,
        assignment_type=ctx.assignment_type,
        subtype=ctx.subtype,
        main_subject=ctx.main_subject,
        related_subjects=ctx.related_subjects,
        reference_document=ctx.reference_document or "none",
        type_guidance=ctx.type_guidance or "none",
        subtype_guidance=ctx.subtype_guidance or "none",
        inquiry_depth=ctx.inquiry_depth,
        submission_mode=ctx.submission_mode,
        duration_weeks=ctx.duration_weeks,
        depth_guidance=ctx.depth_guidance,
        template_json=ctx.template_json,
        rag_section=rag_section,
    )

    return system_prompt, user_prompt


def build_lesson_plan_prompt(ctx: LessonPlanPromptContext) -> tuple[str, str]:
    rag_section = ""
    if ctx.rag_context:
        rag_section = f"\n学科参考片段（仅供约束与细节对齐）：\n{ctx.rag_context}\n"

    system_prompt = load_template("lesson_plan.system.txt")
    user_prompt = load_template("lesson_plan.user.txt").format(
        title=ctx.title,
        topic=ctx.topic,
        school_stage=ctx.school_stage,
        grade=ctx.grade,
        assignment_type=ctx.assignment_type,
        inquiry_depth=ctx.inquiry_depth,
        submission_mode=ctx.submission_mode,
        duration_weeks=ctx.duration_weeks,
        main_subject=ctx.main_subject,
        related_subjects=ctx.related_subjects,
        lesson_plan_excerpt=ctx.lesson_plan_excerpt,
        template_json=ctx.template_json,
        rag_section=rag_section,
    )
    return system_prompt, user_prompt

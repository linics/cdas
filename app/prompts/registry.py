"""Prompt registry metadata for traceability and controlled rollout."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptSpec:
    prompt_id: str
    version: str
    owner: str
    target_api: str
    fallback_policy: str

    def log_label(self) -> str:
        return f"{self.prompt_id}@{self.version}"


ASSIGNMENT_PREVIEW_PROMPT = PromptSpec(
    prompt_id="assignment.preview",
    version="v2.3.0",
    owner="teaching-design",
    target_api="POST /api/v2/assignments/preview",
    fallback_policy="default_objectives+template_phases+default_rubric",
)

ASSIGNMENT_LESSON_PLAN_PROMPT = PromptSpec(
    prompt_id="assignment.from_lesson_plan",
    version="v2.3.0",
    owner="teaching-design",
    target_api="POST /api/v2/assignments/from-lesson-plan",
    fallback_policy="default_objectives+template_phases+default_rubric",
)

EVALUATION_AI_ASSIST_PROMPT = PromptSpec(
    prompt_id="evaluation.ai_assist",
    version="v2.0.0",
    owner="teaching-evaluation",
    target_api="POST /api/v2/evaluations/ai-assist/{submission_id}",
    fallback_policy="fallback_dimension_scores_and_feedback",
)

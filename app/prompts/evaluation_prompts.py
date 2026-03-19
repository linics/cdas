"""Evaluation prompt builders."""

from dataclasses import dataclass

from app.prompts.template_loader import load_template


@dataclass(frozen=True)
class EvaluationPromptContext:
    assignment_title: str
    assignment_topic: str
    assignment_description: str
    objectives_json: str
    phase_context: str
    submission_text: str
    attachments: str
    checkpoints: str
    rubric_text: str


def build_evaluation_prompt(ctx: EvaluationPromptContext) -> tuple[str, str]:
    system_prompt = load_template("evaluation_ai_assist.system.txt")
    user_prompt = load_template("evaluation_ai_assist.user.txt").format(
        assignment_title=ctx.assignment_title,
        assignment_topic=ctx.assignment_topic,
        assignment_description=ctx.assignment_description,
        objectives_json=ctx.objectives_json,
        phase_context=ctx.phase_context,
        submission_text=ctx.submission_text,
        attachments=ctx.attachments,
        checkpoints=ctx.checkpoints,
        rubric_text=ctx.rubric_text,
    )

    return system_prompt, user_prompt

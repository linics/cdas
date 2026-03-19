# ISSUE-009 Prompt Evaluation Sheet

## Purpose

Provide a repeatable sample-based review sheet for prompt quality tuning (assignment preview + lesson-plan generation + grading suggestion).

## Evaluation Dimensions

Score each item on 1-5:

1. Scenario continuity: phase titles and step flow form a clear storyline.
2. Actionability: each step can be executed in real classroom context.
3. Evidence clarity: checkpoint evidence is specific and verifiable.
4. Non-template quality: wording avoids repetitive formula patterns.
5. Teacher edit cost: estimated edits before publish are low.

## Sample Set (10 cases)

| Case | Source Type | Theme | Grade | Assignment Type | Prompt Path |
|---|---|---|---|---|---|
| C01 | lesson plan | 校园垃圾分类改进 | 7 | project | from-lesson-plan |
| C02 | lesson plan | 社区老年人数字关怀 | 8 | inquiry | from-lesson-plan |
| C03 | lesson plan | 本地水质微调查 | 8 | inquiry | from-lesson-plan |
| C04 | lesson plan | 校园植物观察日记 | 7 | practical | from-lesson-plan |
| C05 | lesson plan | 传统节日文化传播 | 7 | project | from-lesson-plan |
| C06 | manual form | 厨余堆肥实验 | 8 | inquiry | preview |
| C07 | manual form | 校园导览短视频 | 7 | practical | preview |
| C08 | manual form | 绿色出行倡议 | 8 | project | preview |
| C09 | manual form | 校园噪声治理建议 | 9 | inquiry | preview |
| C10 | manual form | 班级阅读推广计划 | 7 | project | preview |

## Recording Template

| Case | Continuity | Actionability | Evidence | Non-template | Edit Cost | Notes |
|---|---:|---:|---:|---:|---:|---|
| C01 |  |  |  |  |  |  |
| C02 |  |  |  |  |  |  |
| C03 |  |  |  |  |  |  |
| C04 |  |  |  |  |  |  |
| C05 |  |  |  |  |  |  |
| C06 |  |  |  |  |  |  |
| C07 |  |  |  |  |  |  |
| C08 |  |  |  |  |  |  |
| C09 |  |  |  |  |  |  |
| C10 |  |  |  |  |  |  |

## Acceptance Baseline

- Average score target: >= 4.0 for continuity/actionability/evidence.
- Non-template score target: >= 3.8.
- Teacher edit cost target: >= 4.0.
- Any case with score <= 2 on any dimension must trigger prompt revision.

## Suggested Process

1. Run the 10 cases with fixed seed inputs.
2. Two reviewers score independently.
3. Merge notes and identify top 3 failure patterns.
4. Update prompt constraints once per batch, avoid frequent random tuning.
5. Re-run failed cases after each prompt update.

# 评价规则与 Rubric 重构设计（四档制）

## 背景与目标
当前 v2 实现仍保留了旧版权重与 0-100 分制逻辑，且评价等级使用 A/B/C/D。产品设计书已更新为统一四档评价（优秀/良好/合格/需改进），Rubric 以四档文字描述为核心，取消权重和百分制。目标是在不强制迁移旧数据的前提下，完成服务端评价逻辑与 Rubric 结构的切换，确保 API 输出与设计书一致，AI 生成与 AI 评价也对齐四档规则，并保持一定的兼容性以降低风险。

## 设计范围
- Rubric 结构：`dimensions` 维度包含四档文字描述 `levels`（优秀/良好/合格/需改进）。
- 评分规则：维度评分与总评统一 1–4；总评为维度均值四舍五入。
- 评价等级：`score_level` 枚举语义改为四档等级；响应提供中文标签。
- AI 生成与 AI 评价：提示词与解析逻辑全部切换为四档输出。
- 兼容策略：旧 Rubric/评分输入在服务层归一化，不做批量迁移。

## 数据结构
### Rubric（作业配置）
```
{
  "dimensions": [
    {
      "name": "维度名称",
      "levels": {
        "excellent": "优秀档描述",
        "good": "良好档描述",
        "pass": "合格档描述",
        "improve": "需改进档描述"
      }
    }
  ]
}
```
若 AI 或外部输入提供旧结构（如 `weight/description` 或数组），服务端统一转为 `dimensions + levels`，并对缺失 `levels` 的维度补齐默认描述。

### 评价结果（提交评价）
```
score_level: enum (excellent/good/pass/improve)
score_numeric: 1-4
dimension_scores_json: { "维度名称": 1-4 }
```
API 响应额外返回：
- `score_level_label`: 中文标签（优秀/良好/合格/需改进）
- `dimension_level_labels`: { "维度名称": "中文标签" }

## 评分与等级映射
- 维度评分与总评统一 clamp 至 1–4。
- 总评 = 各维度分数均值四舍五入（如 2.5 → 3）。
- `score_level` 由数值映射：
  - 4 → excellent（优秀）
  - 3 → good（良好）
  - 2 → pass（合格）
  - 1 → improve（需改进）
- 兼容旧输出：
  - A/B/C/D → 4/3/2/1
  - 0–100 → 1–4（90+→4，75+→3，60+→2，其余→1）

## API 变更
### 作业创建/更新
- `rubric_json` 结构变更为四档 `levels`。
- `_normalize_ai_assignment_output` 支持旧格式输入并补齐 `levels`。
- `_default_rubric` 按设计书生成四档 rubric，不再含权重。

### 评价接口
#### 人工评价
`TeacherEvaluationCreate`：
- `score_numeric`: 1–4（可选）
- `score_level`: enum（可选）
- 若缺失，系统按维度均值计算总评并补齐。

#### AI 辅助评价
AI 提示词要求：
- 每个维度给 1–4 评分
- 给出总评分与中文标签
- 返回 JSON：`suggested_score`（1–4）、`suggested_level`、`dimension_scores`、`feedback`、`evidence`

服务端对 AI 输出进行归一化与兜底：
1) clamp 到 1–4  
2) 计算总评均值  
3) 若等级缺失或非法，按总评映射  

## 兼容与迁移策略
- 不进行数据库批量更新。
- 在读写时归一化旧输入，保证 API 输出是新规则。
- `db.py` 保留必要字段更新，但移除或调整对 `score_level` 的强制大写逻辑，避免旧枚举污染新语义。

## 错误处理
错误场景及处理：
- Rubric 缺失或格式错误 → 使用默认 rubric
- 维度评分缺失 → 用总评分或默认 2（合格）补齐
- AI 返回异常 → 使用规则计算结果与兜底文案

## 测试建议
- Rubric 归一化单元测试（旧结构/新结构）
- AI 评分归一化测试（A/B/C/D、0–100、1–4 三类）
- 总评计算测试（均值与边界值）
- API 端到端测试（`score_level_label` 与 `dimension_level_labels` 正确）

## 风险与对策
- 旧数据混用：通过服务层归一化避免读写崩溃。
- 前端展示不一致：API 直接提供中文标签，减少前端推断。
- AI 不稳定：规则层兜底并记录异常日志。

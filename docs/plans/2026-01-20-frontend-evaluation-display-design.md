# 前端评价展示与评分（四档制）设计

## 目标
将前端所有与评价相关的展示与输入统一切换到四档评价（1-4），同时显示中文标签（优秀/良好/合格/需改进），与后端新评价规则一致。

## 范围
- 评分输入：`GradingPage`、`StudentEvaluationPage`
- 展示页面：`StudentSubmissionPage`、`MyAssignmentsPage`
- Rubric 展示：`AssignmentDesignPage`
- API 类型：`frontend/src/lib/api.ts`

## 数据结构与映射
- 等级：`excellent/good/pass/improve`
- 数值：1-4
- 标签：优秀/良好/合格/需改进

前端提供映射工具：
```
scoreValueMap: { excellent: 4, good: 3, pass: 2, improve: 1 }
scoreLabelMap: { excellent: "优秀", good: "良好", pass: "合格", improve: "需改进" }
```

## 页面改动
### 1) GradingPage（教师评分）
- 维度评分：由滑块改为四档单选。
- 总评：自动计算维度平均（四舍五入），可手动微调。
- AI 评分：回填维度单选、总评数值与等级；显示中文标签。
- Rubric 展示：使用 `rubric_json.dimensions[i].levels` 显示四档描述。

### 2) StudentEvaluationPage（自评/互评）
- 维度评分：改为四档单选。
- 仅收集维度评分与评语；总评自动显示但不提交（可选）。
- Rubric 描述：显示四档描述。

### 3) StudentSubmissionPage / MyAssignmentsPage（结果展示）
- 优先使用后端返回的 `score_level_label` 与 `dimension_level_labels`。
- 若标签缺失：由前端映射表推导。
- 展示格式：`中文标签 + 数值(1-4)`。

### 4) AssignmentDesignPage（Rubric 预览）
- 维度展示四档描述，不显示权重/百分制。

## 错误与兼容
- 若 `rubric_json.dimensions` 缺失：提示“未设置评价维度”。
- 若 `score_level_label` 缺失：由 `score_level/score_numeric` 推导。
- AI 评分失败：保留用户当前输入，提示错误。

## 测试建议
- 维度选择后总评自动更新。
- AI 评分回填能正确同步单选。
- 展示页标签优先级逻辑正确（后端标签 > 前端推导）。


# Frontend Alignment Issues

请把你发现的“不符合原前端/逻辑不一致”问题按下面模板写在这个文件里。

## 使用说明

- 一条问题一个小节
- 优先写“会影响主流程”的问题
- 不确定优先级可以先写 `P1`

优先级建议：

- `P0` 阻断主流程（必须先修）
- `P1` 逻辑错误/明显偏差（高优先）
- `P2` 体验或一致性问题（中优先）
- `P3` 文案/样式细节（低优先）

---

## ISSUE-001

- Priority: `P0`
- Page/Path: `登陆页面`
- Current Behavior: 登陆页面有我是教师与我是学生两种登陆选择，现在无论使用哪种选择登陆的平台究竟是学生平台还是教师平台只与账号密码下相关，我不清楚这是原本后端遗留的账号数据权限没有对齐还是本身设计上的问题
- Expected Behavior: 应当正确区分



## ISSUE-002

- Priority: `P1`
- Page/Path: `教师端 设计作业页面`
- Current Behavior: 这部分存在大量问题
1缺失文件导入然后通过ai整合直接成为一个符合规范的作业的格式的功能
2学习目标与任务步骤板块其中 每一个步骤有5个文本框 但是毫无层次逻辑 原本的提示词和现有的前端框架需要同步调整
3底下的评价维度不需要在这里以一个文本框展示 评价维度是跟随作业类型自动调整的 
4页面顶端有一个按键反馈的窗口 但是默认位于页面最顶端 大部分时间都会忽视 请修改为一个临时的页面气泡弹窗 有关闭选择 

## ISSUE-003

- Priority: `P0`
- Page/Path: `知识库`
- Current Behavior: 知识库是这个项目的核心功能 rag功能现在缺失原本拥有的已经分好块的数据库 但是现在丢失了数据 我无法测试是否可用

## ISSUE-004

- Priority: `P1`
- Page/Path: `学生端的作业编辑提交界面`
- Current Behavior:现在提交作业后无论无论教师是否批改都没法进入下一阶段 也可能是现有的作业都是一个阶段完成的 

## ISSUE-005

- Priority: `P1`
- Page/Path: `学生端的作业查看界面`
- Current Behavior:现在教师上传的作业学生端无法正常查看 应当根据年级匹配进行展示 现在学生端展示了诸如Integration Assignment-1772358668_s9qe这样的作业 我不清楚意义为何 但是这不支持

## ISSUE-006

- Priority: `P1`
- Page/Path: `整体数据库`
- Current Behavior:现在我希望对整个后端存储的旧的数据进行一下清理 避免格式不同 与此同时注册新的学生账号和教师账号



## ISSUE-007

- Priority: `P1`
- Page/Path: `作业设计页面的资料导入功能`
- Current Behavior:这里底层逻辑没有问题包括知识库的设计都没有问题 但是存在一个需求就是 当用户拿着一份现成的教案来上传的时候 在设计作业的界面里所有的内容都需要手动填写 而不能根据ai阅读文档直接填写 这个是一个与文档存入知识库不冲突的功能 

## ISSUE-008

- Priority: `P0`
- Page/Path: `作业设计页面`
- Current Behavior:issue2中4页面顶端有一个按键反馈的窗口 但是默认位于页面最顶端 大部分时间都会忽视 请修改为一个临时的页面气泡弹窗 有关闭选择 功能失效了
从教案一键生成会导致请求超时，请稍后重试请排查功能 这里的应该需要一套不同的提示词

## ISSUE-009

- Priority: `P0`
- Page/Path: `作业设计/批改/学生回答`
- Current Behavior:我现在想对我们的一整套核心业务进行一次升级主要聚焦于提示词更新与前端展示的各类逻辑
首先是作业设计页面的提示词第一个是原生的ai预览功能用于生成学习目标与任务步骤 这里任务原本的提示词生成的结果和套公式一样 完全没有任何区分度 所以我这里希望能进行一个大改 能有更加深入的情景设计 可以设计为一段大的情景  后续同时一个个步骤也能有连续的背景设计的作为学习支架 与此同时减少原本每一步骤的框架维度避免 阶段名称 步骤名称 步骤说明 证据要求 课时建议 评价要点 这样多维度 但是里面的内容又缺乏实质用处



---

## 处理状态（2026-03-01）

- ISSUE-006: 已处理
  - 执行选择性清理（仅删除联调残留）
  - 清理结果：`test_users=0`、`integration_assignments=0`
  - 清理脚本：`<repo-root>/scripts/clean_integration_artifacts.py`

- ISSUE-003: 已处理
  - 已恢复并重建课标知识库基础数据（15 份），并标记为 `source=system`
  - 前端改为展示系统知识库 chunks 概览，不再逐条展示内置文件
  - 导入脚本：`<repo-root>/scripts/seed_knowledge_base.py`
  - 页面：`src/app/pages/KnowledgeBase.tsx`

- ISSUE-001: 已处理（后端强校验 + 前端兜底）
  - 登录时若“身份切换选择”和账号真实角色不一致，后端直接拒绝登录并返回提示
  - 前端保留兜底校验，防止进入错误端
  - 代码：`src/app/pages/Auth.tsx`
  - 代码：`<repo-root>/app/api/v2/auth.py`

- ISSUE-002: 已处理（本轮）
  - 已完成：步骤编辑层次优化、评价维度改为自动策略、顶部反馈改为可关闭浮动气泡
  - 已完成：设计作业页支持直接上传参考资料，并选择文档作为 AI 预览/生成的优先参考源
  - 已完成：后端作业 API 支持 `document_id`，预览/创建/更新均可绑定参考文档
  - 代码：`src/app/pages/AssignmentDesigner.tsx`
  - 代码：`src/app/lib/api.ts`
  - 代码：`<repo-root>/app/api/v2/assignments.py`
  - 代码：`<repo-root>/app/services/inventory.py`

- ISSUE-005: 已处理（数据基线）
  - 学生端异常的 `Integration Assignment-*` 测试作业已清理

- ISSUE-007: 已处理（本轮）
  - 新增「从教案一键生成」能力：上传并选择已入库教案后，可直接生成可编辑作业草稿并自动回填页面。
  - 生成内容包含：标题、主题、学段年级、学科、作业类型、目标、步骤与评价维度。
  - 保持与知识库不冲突：仍复用同一文档入库链路，仅新增草稿生成入口。
  - 代码：`src/app/pages/AssignmentDesigner.tsx`
  - 代码：`src/app/lib/api.ts`
  - 代码：`<repo-root>/app/api/v2/assignments.py`

- ISSUE-008: 已处理（本轮）
  - 已排查当前全部 AI 提示词入口：
    - 作业生成：`app/api/v2/assignments.py`（通用生成 + 教案一键生成）
    - 评分建议：`app/api/v2/evaluations.py`
  - 已修复作业生成通用提示词乱码，重写为结构化、可约束的 JSON 输出提示。
  - 已为「从教案一键生成」新增独立提示词与独立生成路径，避免复用过重提示词造成超时。
  - 已优化超时策略：
    - 前端该接口超时从默认 30s 提升为 90s
    - 后端教案专用 AI 请求超时设为 25s（失败快速回退默认模板，避免长时间卡住）
  - 已修复反馈体验：作业设计页错误信息统一进入可关闭的右下气泡（含超时提示）。
  - 代码：`src/app/pages/AssignmentDesigner.tsx`
  - 代码：`src/app/lib/api.ts`
  - 代码：`<repo-root>/app/api/v2/assignments.py`
  - 代码：`<repo-root>/app/services/ai.py`

- ISSUE-009: 进行中（本轮启动）
  - 已新增详细约束文档：`docs/integration/issue-009-prompt-ui-spec.md`
  - 已新增样本评估模板：`docs/integration/issue-009-prompt-evaluation-sheet.md`
  - 已落地第一批改造：
    - 作业生成提示词增加“主线情境连续性 + 学习支架 + 去模板化”约束
    - 教案一键生成提示词增加专用连续情境与简洁步骤约束
    - 作业设计页步骤编辑改为默认三字段（任务动作/学习支架/提交证据），高级字段折叠可选
  - 已落地第二批改造：
    - AI 辅助评分提示词升级为“证据绑定评分”，要求维度分数与量表严格对齐，并输出可执行改进项
    - 学生作业阶段展示升级为“情境导引 + 学习支架 + 提交证据”结构化呈现
  - 已落地第三批改造：
    - 学生侧提交输入区新增“阶段证据检查清单”，支持一键插入证据条目到提交内容
    - 提交内容输入框占位提示改为随当前阶段证据动态联动
  - 已完成首轮 10 案例提示词评估与报告输出：
    - 评估模板：`docs/integration/issue-009-prompt-evaluation-sheet.md`
    - 评估结果（JSON）：`docs/integration/issue-009-prompt-evaluation-results.json`
    - 评估结果（Markdown）：`docs/integration/issue-009-prompt-evaluation-results.md`
    - 自动化脚本：`scripts/run_prompt_sample_eval.py`
    - 本轮结果摘要：平均连续性 `5.0`、可执行性 `5.0`、证据清晰度 `4.4`、非模板化 `5.0`、编辑成本 `5.0`
  - 下一批待完成：
    - 根据首轮评估结果定向提升“证据清晰度（4.4）”并复测

- ISSUE-004: 待复测
  - 后端已支持多阶段 `next_submission_id` 流转；需基于你创建的多阶段作业复测确认
  - 本轮补充：提交后提示语已区分「一次性模式」「已完成全部阶段」「异常未生成下一阶段」三种情况
  - 代码：`src/app/pages/AssignmentDetail.tsx`

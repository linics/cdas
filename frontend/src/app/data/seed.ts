import type { AssignmentDraft, ClassGroup, ClassRoom, LessonStep, UserAccount } from "./models";
import { getLegacyAuthState, saveAssignments, saveClasses, saveGroups, saveUsers, setCurrentUserId, STORAGE_KEYS, clearLegacyAuthKeys } from "./storage";

const TEACHER_ID = "teacher_zhang";
const STUDENT_ID = "student_lixh";
const CLASS_ID = "class_j8_3";
const GROUP_ID = "group_env";

const defaultSteps: LessonStep[] = [
  {
    id: "step_plan",
    phaseName: "准备与规划",
    stepName: "提出问题并设计取样方案",
    learningGoal: "明确可检验问题，完成点位选择与变量控制。",
    teacherActivity: "展示水质案例，示范如何确定点位和控制变量。",
    studentActivity: "小组讨论研究问题，绘制点位图并确定分工。",
    learningSupport: "取样方案模板、安全清单、指标说明卡。",
    evidence: "《取样与检测方案》、小组分工表、点位草图。",
    evaluationPoints: "问题可检验、点位有代表性、分工清晰。",
    lessonTimeSuggestion: "1课时",
  },
  {
    id: "step_detect",
    phaseName: "取样与检测",
    stepName: "开展现场取样与指标检测",
    learningGoal: "按规范完成 pH/浊度等指标检测并形成可追溯记录。",
    teacherActivity: "讲解器材使用与安全规范，巡视纠偏。",
    studentActivity: "按流程取样、重复测量、拍照留证并记录原始数据。",
    learningSupport: "操作流程图、记录表模板、示范视频。",
    evidence: "原始记录表、现场照片、检测视频片段。",
    evaluationPoints: "操作规范、记录完整、证据链连续。",
    lessonTimeSuggestion: "1课时",
  },
  {
    id: "step_analyze",
    phaseName: "数据分析与解释",
    stepName: "统计可视化与原因链条构建",
    learningGoal: "用图表比较点位差异并解释可能原因。",
    teacherActivity: "提供图表模板，指导异常值和误差分析。",
    studentActivity: "清洗数据、计算统计量、绘制图表、构建解释框架。",
    learningSupport: "电子表格模板、图表样例、误差分析提示卡。",
    evidence: "统计表、可视化图表、解释框架图。",
    evaluationPoints: "结论与数据一致，解释具备证据支撑。",
    lessonTimeSuggestion: "1课时",
  },
  {
    id: "step_present",
    phaseName: "成果表达与公共参与",
    stepName: "完成报告与展示答辩",
    learningGoal: "形成调查报告并提出可执行建议。",
    teacherActivity: "提供报告结构模板并组织同伴互评。",
    studentActivity: "完成报告与海报/视频，进行 3 分钟汇报答辩。",
    learningSupport: "报告模板、评价量规、答辩提示卡。",
    evidence: "调查报告、展示作品、倡议书。",
    evaluationPoints: "结构完整、证据充分、建议可落地。",
    lessonTimeSuggestion: "1课时",
  },
];

const seedUsers: UserAccount[] = [
  {
    id: TEACHER_ID,
    role: "teacher",
    name: "张老师",
    phone: "13800138000",
    workerId: "T2026001",
    password: "Pass1234",
    joinedClassIds: [],
    createdAt: "2026-02-01T00:00:00.000Z",
  },
  {
    id: STUDENT_ID,
    role: "student",
    name: "李小华",
    phone: "13900139000",
    studentId: "S2026001",
    password: "Pass1234",
    joinedClassIds: [CLASS_ID],
    createdAt: "2026-02-01T00:00:00.000Z",
  },
];

const seedClasses: ClassRoom[] = [
  {
    id: CLASS_ID,
    teacherId: TEACHER_ID,
    name: "八年级3班",
    gradeId: "j8",
    inviteCode: "A8K3M2Q9",
    groupIds: [GROUP_ID],
    studentIds: [STUDENT_ID],
    createdAt: "2026-02-01T00:00:00.000Z",
  },
];

const seedGroups: ClassGroup[] = [
  {
    id: GROUP_ID,
    classId: CLASS_ID,
    name: "环境探究组",
    memberStudentIds: [STUDENT_ID],
  },
];

const seedAssignments: AssignmentDraft[] = [
  {
    id: "assignment_water_quality",
    teacherId: TEACHER_ID,
    title: "家乡水质情况探究",
    schoolLevel: "初中",
    grade: "j8",
    mainSubject: "science",
    integratedSubjects: ["geography", "math", "infoTech", "chinese", "politics"],
    type: "project",
    depth: "deep",
    crossConcepts: ["system_model", "stability_change"],
    description: "围绕家乡水体开展取样、检测、分析与改进建议发布。",
    detailedSteps: defaultSteps,
    targetClassIds: [CLASS_ID],
    status: "published",
    createdAt: "2026-02-10T00:00:00.000Z",
    updatedAt: "2026-02-20T00:00:00.000Z",
  },
  {
    id: "assignment_carbon",
    teacherId: TEACHER_ID,
    title: "家庭碳排放量量化研究",
    schoolLevel: "初中",
    grade: "j8",
    mainSubject: "science",
    integratedSubjects: ["math", "geography"],
    type: "project",
    depth: "deep",
    crossConcepts: ["matter_energy"],
    description: "记录家庭能源消耗并建立量化模型，提出减排建议。",
    detailedSteps: defaultSteps,
    targetClassIds: [CLASS_ID],
    status: "published",
    createdAt: "2026-02-01T00:00:00.000Z",
    updatedAt: "2026-02-22T00:00:00.000Z",
  },
  {
    id: "assignment_draft_culture",
    teacherId: TEACHER_ID,
    title: "家乡民俗文化调查（草稿）",
    schoolLevel: "初中",
    grade: "j8",
    mainSubject: "chinese",
    integratedSubjects: ["history", "arts"],
    type: "inquiry",
    depth: "medium",
    crossConcepts: ["structure_function"],
    description: "围绕家乡民俗完成访谈、史料梳理与展示。",
    detailedSteps: defaultSteps,
    targetClassIds: [],
    status: "draft",
    createdAt: "2026-02-15T00:00:00.000Z",
    updatedAt: "2026-02-25T00:00:00.000Z",
  },
];

function hasInitialized(): boolean {
  return (
    !!localStorage.getItem(STORAGE_KEYS.users) &&
    !!localStorage.getItem(STORAGE_KEYS.classes) &&
    !!localStorage.getItem(STORAGE_KEYS.assignments)
  );
}

function migrateLegacyAuthIfNeeded(): void {
  const { isLoggedIn, role } = getLegacyAuthState();
  if (!isLoggedIn || !role) {
    clearLegacyAuthKeys();
    return;
  }

  if (role === "teacher") {
    setCurrentUserId(TEACHER_ID);
  } else {
    setCurrentUserId(STUDENT_ID);
  }

  clearLegacyAuthKeys();
}

export function ensureSeedData(): void {
  if (!hasInitialized()) {
    saveUsers(seedUsers);
    saveClasses(seedClasses);
    saveGroups(seedGroups);
    saveAssignments(seedAssignments);
    localStorage.setItem(STORAGE_KEYS.lessonPlans, JSON.stringify([]));
  }

  migrateLegacyAuthIfNeeded();
}

export { defaultSteps };

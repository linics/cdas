import {
  BookOpen,
  Palette,
  Dna,
  Atom,
  Globe,
  Calculator,
  History,
  Gavel,
  Monitor,
  Activity,
  Hammer,
  Star,
  Layers,
  GraduationCap,
} from "lucide-react";
import type {
  AssignmentTypeDef,
  CrossConceptDef,
  DepthLevelDef,
  GradeDef,
  SchoolLevel,
  SubjectDef,
} from "./models";

export const PRIMARY_SCHOOL_SUBJECT_IDS = [
  "politics",
  "chinese",
  "math",
  "english",
  "science",
  "infoTech",
  "labor",
  "arts",
  "sports",
  "integrated",
] as const;

export const JUNIOR_SCHOOL_SUBJECT_IDS = [
  "politics",
  "chinese",
  "math",
  "english",
  "history",
  "geography",
  "physics",
  "chemistry",
  "biology",
  "infoTech",
  "labor",
  "arts",
  "sports",
  "integrated",
] as const;

export const SUBJECTS: SubjectDef[] = [
  {
    id: "politics",
    name: "道德与法治",
    icon: Gavel,
    color: "text-subject-humanities",
    category: "人文社科",
    schoolLevels: ["小学", "初中"],
  },
  {
    id: "chinese",
    name: "语文",
    icon: BookOpen,
    color: "text-subject-humanities",
    category: "人文社科",
    schoolLevels: ["小学", "初中"],
  },
  {
    id: "history",
    name: "历史",
    icon: History,
    color: "text-subject-humanities",
    category: "人文社科",
    schoolLevels: ["初中"],
  },
  {
    id: "geography",
    name: "地理",
    icon: Globe,
    color: "text-subject-humanities",
    category: "人文社科",
    schoolLevels: ["初中"],
  },
  {
    id: "english",
    name: "英语",
    icon: Star,
    color: "text-subject-humanities",
    category: "人文社科",
    schoolLevels: ["小学", "初中"],
  },
  {
    id: "science",
    name: "科学",
    icon: Atom,
    color: "text-subject-science",
    category: "自然科学",
    schoolLevels: ["小学", "初中"],
  },
  {
    id: "physics",
    name: "物理",
    icon: Layers,
    color: "text-subject-science",
    category: "自然科学",
    schoolLevels: ["初中"],
  },
  {
    id: "chemistry",
    name: "化学",
    icon: Atom,
    color: "text-subject-science",
    category: "自然科学",
    schoolLevels: ["初中"],
  },
  {
    id: "biology",
    name: "生物学",
    icon: Dna,
    color: "text-subject-science",
    category: "自然科学",
    schoolLevels: ["初中"],
  },
  {
    id: "math",
    name: "数学",
    icon: Calculator,
    color: "text-subject-science",
    category: "自然科学",
    schoolLevels: ["小学", "初中"],
  },
  {
    id: "infoTech",
    name: "信息科技",
    icon: Monitor,
    color: "text-subject-tech",
    category: "技术类",
    schoolLevels: ["小学", "初中"],
  },
  {
    id: "labor",
    name: "劳动",
    icon: Hammer,
    color: "text-subject-tech",
    category: "技术类",
    schoolLevels: ["小学", "初中"],
  },
  {
    id: "arts",
    name: "艺术",
    icon: Palette,
    color: "text-subject-arts",
    category: "艺体类",
    schoolLevels: ["小学", "初中"],
  },
  {
    id: "sports",
    name: "体育与健康",
    icon: Activity,
    color: "text-subject-arts",
    category: "艺体类",
    schoolLevels: ["小学", "初中"],
  },
  {
    id: "integrated",
    name: "综合实践活动",
    icon: GraduationCap,
    color: "text-subject-integrated",
    category: "综合类",
    schoolLevels: ["小学", "初中"],
  },
];

export const GRADES: GradeDef[] = [
  { id: "p1", name: "一年级", school: "小学" },
  { id: "p2", name: "二年级", school: "小学" },
  { id: "p3", name: "三年级", school: "小学" },
  { id: "p4", name: "四年级", school: "小学" },
  { id: "p5", name: "五年级", school: "小学" },
  { id: "p6", name: "六年级", school: "小学" },
  { id: "j7", name: "七年级", school: "初中" },
  { id: "j8", name: "八年级", school: "初中" },
  { id: "j9", name: "九年级", school: "初中" },
];

export const ASSIGNMENT_TYPES: AssignmentTypeDef[] = [
  { id: "practical", name: "实践性作业", desc: "体验、观察、参与真实情境" },
  { id: "inquiry", name: "探究性作业", desc: "调查、实验、论证科学问题" },
  { id: "project", name: "项目式作业", desc: "设计、制作、迭代解决现实问题" },
];

export const DEPTH_LEVELS: DepthLevelDef[] = [
  { id: "basic", name: "基础探究", desc: "理解与掌握核心概念" },
  { id: "medium", name: "中等探究", desc: "情境化运用知识解决问题" },
  { id: "deep", name: "深度探究", desc: "跨学科综合探究与方案设计" },
];

export const CROSS_CONCEPTS: CrossConceptDef[] = [
  { id: "matter_energy", name: "物质与能量", desc: "形态转化与守恒" },
  { id: "structure_function", name: "结构与功能", desc: "设计与适应性" },
  { id: "system_model", name: "系统与模型", desc: "简化研究工具" },
  { id: "stability_change", name: "稳定与变化", desc: "相对平衡与绝对发展" },
];

export function getSubjectsBySchoolLevel(level: SchoolLevel): SubjectDef[] {
  return SUBJECTS.filter((subject) => subject.schoolLevels.includes(level));
}

export const CORE_COMPETENCIES = {
  chinese: ["文化自信", "语言运用", "思维能力", "审美创造"],
  math: ["数感/抽象能力", "运算能力", "几何直观", "推理能力", "模型观念", "创新意识"],
  science: ["科学观念", "科学思维", "探究实践", "态度责任"],
  physics: ["物理观念", "科学思维", "科学探究", "科学态度与责任"],
  history: ["唯物史观", "时空观念", "史料实证", "历史解释", "家国情怀"],
};

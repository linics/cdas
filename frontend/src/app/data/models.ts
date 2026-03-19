export type Role = "teacher" | "student";

export type SchoolLevel = "小学" | "初中";

export type AssignmentStatus = "draft" | "published" | "archived";

export interface UserAccount {
  id: string;
  role: Role;
  name: string;
  phone: string;
  workerId?: string;
  studentId?: string;
  password: string;
  joinedClassIds: string[];
  createdAt: string;
}

export interface SubjectDef {
  id: string;
  name: string;
  category: string;
  icon: any;
  color: string;
  schoolLevels: SchoolLevel[];
}

export interface GradeDef {
  id: string;
  name: string;
  school: SchoolLevel;
}

export interface AssignmentTypeDef {
  id: string;
  name: string;
  desc: string;
}

export interface DepthLevelDef {
  id: string;
  name: string;
  desc: string;
}

export interface CrossConceptDef {
  id: string;
  name: string;
  desc: string;
}

export interface ClassGroup {
  id: string;
  classId: string;
  name: string;
  memberStudentIds: string[];
}

export interface ClassRoom {
  id: string;
  teacherId: string;
  name: string;
  gradeId: string;
  inviteCode: string;
  groupIds: string[];
  studentIds: string[];
  createdAt: string;
}

export interface LessonStep {
  id: string;
  phaseName: string;
  stepName: string;
  learningGoal: string;
  teacherActivity: string;
  studentActivity: string;
  learningSupport: string;
  evidence: string;
  evaluationPoints: string;
  lessonTimeSuggestion: string;
}

export interface AssignmentDraft {
  id: string;
  teacherId: string;
  title: string;
  schoolLevel: SchoolLevel;
  grade: string;
  mainSubject: string;
  integratedSubjects: string[];
  type: string;
  depth: string;
  crossConcepts: string[];
  description: string;
  detailedSteps: LessonStep[];
  targetClassIds: string[];
  status: AssignmentStatus;
  updatedAt: string;
  createdAt: string;
}

export interface LessonSection {
  title: string;
  content: string;
}

export interface LessonPlanDocument {
  assignmentId: string;
  title: string;
  sections: LessonSection[];
  generatedAt: string;
}

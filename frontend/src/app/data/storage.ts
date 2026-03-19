import type {
  AssignmentDraft,
  AssignmentStatus,
  ClassGroup,
  ClassRoom,
  LessonPlanDocument,
  Role,
  SchoolLevel,
  UserAccount,
} from "./models";
import { generateId, nowIso } from "../utils/id";
import { generateInviteCode } from "../utils/inviteCode";

export const STORAGE_KEYS = {
  users: "cdas_users",
  currentUserId: "cdas_current_user_id",
  classes: "cdas_classes",
  groups: "cdas_groups",
  assignments: "cdas_assignments",
  lessonPlans: "cdas_lesson_plan_docs",
} as const;

function safeParse<T>(raw: string | null, fallback: T): T {
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function readList<T>(key: string): T[] {
  return safeParse<T[]>(localStorage.getItem(key), []);
}

function writeList<T>(key: string, data: T[]): void {
  localStorage.setItem(key, JSON.stringify(data));
}

export function getUsers(): UserAccount[] {
  return readList<UserAccount>(STORAGE_KEYS.users);
}

export function saveUsers(users: UserAccount[]): void {
  writeList(STORAGE_KEYS.users, users);
}

export function getCurrentUserId(): string | null {
  return localStorage.getItem(STORAGE_KEYS.currentUserId);
}

export function setCurrentUserId(userId: string): void {
  localStorage.setItem(STORAGE_KEYS.currentUserId, userId);
}

export function clearCurrentUserId(): void {
  localStorage.removeItem(STORAGE_KEYS.currentUserId);
}

export function getCurrentUser(): UserAccount | null {
  const currentId = getCurrentUserId();
  if (!currentId) return null;
  return getUsers().find((u) => u.id === currentId) ?? null;
}

export function updateUser(userId: string, updater: (user: UserAccount) => UserAccount): UserAccount | null {
  const users = getUsers();
  const index = users.findIndex((u) => u.id === userId);
  if (index < 0) return null;
  const next = updater(users[index]);
  users[index] = next;
  saveUsers(users);
  return next;
}

interface RegisterPayload {
  role: Role;
  name: string;
  phone: string;
  password: string;
  workerId?: string;
  studentId?: string;
}

export interface DeleteClassRoomResult {
  ok: boolean;
  message: string;
  removedGroupCount?: number;
  removedStudentCount?: number;
  affectedAssignmentCount?: number;
}

export function createUser(payload: RegisterPayload): { ok: boolean; message: string; user?: UserAccount } {
  const users = getUsers();

  const phoneExists = users.some((u) => u.phone === payload.phone);
  if (phoneExists) {
    return { ok: false, message: "该手机号已注册" };
  }

  if (payload.role === "teacher") {
    const workerId = (payload.workerId || "").trim();
    if (!workerId) return { ok: false, message: "教师工号不能为空" };
    const exists = users.some((u) => u.role === "teacher" && u.workerId === workerId);
    if (exists) return { ok: false, message: "该工号已注册" };
  }

  if (payload.role === "student") {
    const studentId = (payload.studentId || "").trim();
    if (!studentId) return { ok: false, message: "学生学号不能为空" };
    const exists = users.some((u) => u.role === "student" && u.studentId === studentId);
    if (exists) return { ok: false, message: "该学号已注册" };
  }

  const now = nowIso();
  const user: UserAccount = {
    id: generateId(payload.role),
    role: payload.role,
    name: payload.name,
    phone: payload.phone,
    password: payload.password,
    workerId: payload.role === "teacher" ? payload.workerId : undefined,
    studentId: payload.role === "student" ? payload.studentId : undefined,
    joinedClassIds: [],
    createdAt: now,
  };

  saveUsers([...users, user]);
  return { ok: true, message: "注册成功", user };
}

export function authenticateUser(role: Role, identifier: string, password: string): UserAccount | null {
  const users = getUsers();
  return (
    users.find((u) => {
      if (u.role !== role || u.password !== password) return false;
      if (role === "teacher") {
        return u.phone === identifier || u.workerId === identifier;
      }
      return u.phone === identifier || u.studentId === identifier;
    }) ?? null
  );
}

export function getClasses(): ClassRoom[] {
  return readList<ClassRoom>(STORAGE_KEYS.classes);
}

export function saveClasses(classes: ClassRoom[]): void {
  writeList(STORAGE_KEYS.classes, classes);
}

export function getGroups(): ClassGroup[] {
  return readList<ClassGroup>(STORAGE_KEYS.groups);
}

export function saveGroups(groups: ClassGroup[]): void {
  writeList(STORAGE_KEYS.groups, groups);
}

function generateUniqueInvite(existingCodes: string[]): string {
  let code = generateInviteCode(8);
  while (existingCodes.includes(code)) {
    code = generateInviteCode(8);
  }
  return code;
}

export function createClassRoom(teacherId: string, name: string, gradeId: string): ClassRoom {
  const classes = getClasses();
  const code = generateUniqueInvite(classes.map((c) => c.inviteCode));
  const next: ClassRoom = {
    id: generateId("class"),
    teacherId,
    name,
    gradeId,
    inviteCode: code,
    groupIds: [],
    studentIds: [],
    createdAt: nowIso(),
  };
  saveClasses([...classes, next]);
  return next;
}

export function regenerateClassInviteCode(classId: string): ClassRoom | null {
  const classes = getClasses();
  const current = classes.find((c) => c.id === classId);
  if (!current) return null;
  const code = generateUniqueInvite(classes.filter((c) => c.id !== classId).map((c) => c.inviteCode));
  const next = classes.map((c) => (c.id === classId ? { ...c, inviteCode: code } : c));
  saveClasses(next);
  return next.find((c) => c.id === classId) ?? null;
}

export function deleteClassRoom(classId: string, teacherId: string): DeleteClassRoomResult {
  const classes = getClasses();
  const target = classes.find((item) => item.id === classId);
  if (!target) {
    return { ok: false, message: "班级不存在" };
  }

  if (target.teacherId !== teacherId) {
    return { ok: false, message: "无权限删除该班级" };
  }

  const nextClasses = classes.filter((item) => item.id !== classId);
  saveClasses(nextClasses);

  const groups = getGroups();
  const removedGroupCount = groups.filter((group) => group.classId === classId).length;
  const nextGroups = groups.filter((group) => group.classId !== classId);
  saveGroups(nextGroups);

  const users = getUsers();
  let removedStudentCount = 0;
  const nextUsers = users.map((user) => {
    if (user.role !== "student" || !user.joinedClassIds.includes(classId)) return user;
    removedStudentCount += 1;
    return {
      ...user,
      joinedClassIds: user.joinedClassIds.filter((id) => id !== classId),
    };
  });
  saveUsers(nextUsers);

  const assignments = getAssignments();
  let affectedAssignmentCount = 0;
  const nextAssignments = assignments.map((assignment) => {
    if (!assignment.targetClassIds.includes(classId)) return assignment;
    affectedAssignmentCount += 1;
    return {
      ...assignment,
      targetClassIds: assignment.targetClassIds.filter((id) => id !== classId),
      updatedAt: nowIso(),
    };
  });
  saveAssignments(nextAssignments);

  return {
    ok: true,
    message: `班级已删除：清理${removedGroupCount}个小组、${removedStudentCount}名学生关系、${affectedAssignmentCount}个作业发布对象`,
    removedGroupCount,
    removedStudentCount,
    affectedAssignmentCount,
  };
}

export function createClassGroup(classId: string, name: string): ClassGroup | null {
  const classes = getClasses();
  if (!classes.some((c) => c.id === classId)) return null;

  const groups = getGroups();
  const group: ClassGroup = {
    id: generateId("group"),
    classId,
    name,
    memberStudentIds: [],
  };
  saveGroups([...groups, group]);

  const updatedClasses = classes.map((c) =>
    c.id === classId ? { ...c, groupIds: [...c.groupIds, group.id] } : c,
  );
  saveClasses(updatedClasses);

  return group;
}

export function assignStudentToGroup(classId: string, groupId: string, studentId: string): { ok: boolean; message: string } {
  const classes = getClasses();
  const targetClass = classes.find((c) => c.id === classId);
  if (!targetClass) return { ok: false, message: "班级不存在" };
  if (!targetClass.studentIds.includes(studentId)) return { ok: false, message: "学生尚未加入该班级" };

  const groups = getGroups();
  const classGroups = groups.filter((g) => g.classId === classId);
  if (!classGroups.some((g) => g.id === groupId)) return { ok: false, message: "小组不存在" };

  const cleaned = groups.map((g) => {
    if (g.classId !== classId) return g;
    return { ...g, memberStudentIds: g.memberStudentIds.filter((id) => id !== studentId) };
  });

  const assigned = cleaned.map((g) =>
    g.id === groupId ? { ...g, memberStudentIds: [...g.memberStudentIds, studentId] } : g,
  );

  saveGroups(assigned);
  return { ok: true, message: "分组已更新" };
}

export function joinClassByInviteCode(studentId: string, inviteCode: string): { ok: boolean; message: string; classRoom?: ClassRoom } {
  const normalized = inviteCode.trim().toUpperCase();
  const classes = getClasses();
  const target = classes.find((c) => c.inviteCode === normalized);

  if (!target) {
    return { ok: false, message: "邀请码不存在（当前设备数据中）" };
  }

  if (target.studentIds.includes(studentId)) {
    return { ok: false, message: "你已经加入该班级", classRoom: target };
  }

  const updatedClass: ClassRoom = {
    ...target,
    studentIds: [...target.studentIds, studentId],
  };

  const nextClasses = classes.map((c) => (c.id === target.id ? updatedClass : c));
  saveClasses(nextClasses);

  const users = getUsers();
  const nextUsers = users.map((u) => {
    if (u.id !== studentId) return u;
    const joinedClassIds = u.joinedClassIds.includes(target.id)
      ? u.joinedClassIds
      : [...u.joinedClassIds, target.id];
    return { ...u, joinedClassIds };
  });
  saveUsers(nextUsers);

  return { ok: true, message: "加入班级成功", classRoom: updatedClass };
}

export function getAssignments(): AssignmentDraft[] {
  return readList<AssignmentDraft>(STORAGE_KEYS.assignments);
}

export function saveAssignments(assignments: AssignmentDraft[]): void {
  writeList(STORAGE_KEYS.assignments, assignments);
}

export function upsertAssignment(assignment: AssignmentDraft): AssignmentDraft {
  const all = getAssignments();
  const idx = all.findIndex((a) => a.id === assignment.id);
  const next = {
    ...assignment,
    updatedAt: nowIso(),
  };
  if (idx >= 0) {
    all[idx] = next;
    saveAssignments(all);
    return next;
  }
  saveAssignments([...all, next]);
  return next;
}

export function createAssignmentDraft(payload: Omit<AssignmentDraft, "id" | "createdAt" | "updatedAt">): AssignmentDraft {
  const now = nowIso();
  const assignment: AssignmentDraft = {
    ...payload,
    id: generateId("assignment"),
    createdAt: now,
    updatedAt: now,
  };
  saveAssignments([...getAssignments(), assignment]);
  return assignment;
}

export function deleteDraftAssignment(assignmentId: string): boolean {
  const assignments = getAssignments();
  const target = assignments.find((a) => a.id === assignmentId);
  if (!target || target.status !== "draft") return false;
  saveAssignments(assignments.filter((a) => a.id !== assignmentId));
  return true;
}

export function updateAssignmentStatus(assignmentId: string, status: AssignmentStatus): AssignmentDraft | null {
  const all = getAssignments();
  const idx = all.findIndex((a) => a.id === assignmentId);
  if (idx < 0) return null;

  const current = all[idx];
  if (current.status === "draft" && status === "published") {
    all[idx] = { ...current, status, updatedAt: nowIso() };
  } else if (current.status === "published" && status === "archived") {
    all[idx] = { ...current, status, updatedAt: nowIso() };
  } else if (current.status === "archived" && status === "published") {
    all[idx] = { ...current, status, updatedAt: nowIso() };
  } else {
    return null;
  }

  saveAssignments(all);
  return all[idx];
}

export function duplicateAssignment(assignmentId: string, teacherId: string): AssignmentDraft | null {
  const source = getAssignments().find((a) => a.id === assignmentId);
  if (!source) return null;

  return createAssignmentDraft({
    ...source,
    teacherId,
    title: `${source.title}（副本）`,
    status: "draft",
    targetClassIds: [],
  });
}

export function getTeacherAssignments(teacherId: string): AssignmentDraft[] {
  return getAssignments()
    .filter((a) => a.teacherId === teacherId)
    .sort((a, b) => (a.updatedAt > b.updatedAt ? -1 : 1));
}

export function getStudentAssignments(studentId: string): AssignmentDraft[] {
  const users = getUsers();
  const student = users.find((u) => u.id === studentId && u.role === "student");
  if (!student) return [];

  return getAssignments()
    .filter((a) => a.status === "published")
    .filter((a) => a.targetClassIds.some((id) => student.joinedClassIds.includes(id)))
    .sort((a, b) => (a.updatedAt > b.updatedAt ? -1 : 1));
}

export function getLessonPlanDocs(): LessonPlanDocument[] {
  return readList<LessonPlanDocument>(STORAGE_KEYS.lessonPlans);
}

export function saveLessonPlanDoc(doc: LessonPlanDocument): void {
  const docs = getLessonPlanDocs();
  const next = docs.filter((d) => d.assignmentId !== doc.assignmentId);
  writeList(STORAGE_KEYS.lessonPlans, [...next, doc]);
}

export function getClassesByTeacher(teacherId: string): ClassRoom[] {
  return getClasses().filter((c) => c.teacherId === teacherId);
}

export function getClassGroups(classId: string): ClassGroup[] {
  return getGroups().filter((g) => g.classId === classId);
}

export function getStudentsByIds(studentIds: string[]): UserAccount[] {
  const users = getUsers().filter((u) => u.role === "student");
  return users.filter((u) => studentIds.includes(u.id));
}

export function getGroupForStudentInClass(classId: string, studentId: string): ClassGroup | null {
  return getGroups().find((g) => g.classId === classId && g.memberStudentIds.includes(studentId)) ?? null;
}

export function isTeacherOfClass(classId: string, teacherId: string): boolean {
  return getClasses().some((c) => c.id === classId && c.teacherId === teacherId);
}

export function clearLegacyAuthKeys(): void {
  localStorage.removeItem("isLoggedIn");
  localStorage.removeItem("userRole");
}

export function getLegacyAuthState(): { isLoggedIn: boolean; role: Role | null } {
  const isLoggedIn = localStorage.getItem("isLoggedIn") === "true";
  const role = localStorage.getItem("userRole") as Role | null;
  return { isLoggedIn, role };
}

export function filterSubjectsBySchoolLevel<T extends { schoolLevels?: SchoolLevel[] }>(
  list: T[],
  schoolLevel: SchoolLevel,
): T[] {
  return list.filter((item) => !item.schoolLevels || item.schoolLevels.includes(schoolLevel));
}

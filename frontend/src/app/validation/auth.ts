import type { UserRole } from "../lib/api";

const PHONE_REGEX = /^1[3-9]\d{9}$/;
const IDENTIFIER_REGEX = /^[A-Za-z0-9_-]{4,32}$/;

export interface AuthRegisterInput {
  role: UserRole;
  name: string;
  identifier: string;
  password: string;
  grade?: number;
  className?: string;
  phone?: string;
}

export function validateLoginInput(identifier: string, password: string, label: string): string | null {
  if (!identifier.trim()) return `请输入${label}`;
  if (!password || password.trim().length < 8) return "请输入至少 8 位密码";
  return null;
}

export function validateRegisterInput(input: AuthRegisterInput): string | null {
  if (!input.name.trim()) return "请输入姓名";
  if (!IDENTIFIER_REGEX.test(input.identifier.trim())) {
    return `${input.role === "teacher" ? "工号" : "学号"}格式应为 4-32 位字母、数字、下划线或连字符`;
  }
  if (input.phone?.trim() && !PHONE_REGEX.test(input.phone.trim())) {
    return "手机号格式不正确";
  }
  const password = input.password.trim();
  if (password.length < 8) return "密码至少 8 位";
  if (input.role === "student") {
    if (!Number.isFinite(input.grade) || (input.grade || 0) < 1 || (input.grade || 0) > 9) {
      return "学生年级需在 1-9 之间";
    }
    if (!input.className?.trim()) return "请输入班级名称";
  }
  return null;
}

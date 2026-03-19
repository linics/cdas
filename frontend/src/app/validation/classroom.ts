const INVITE_CODE_REGEX = /^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{4,16}$/;

export function validateClassroomName(name: string): string | null {
  const value = name.trim();
  if (!value) return "请输入班级名称";
  if (value.length > 100) return "班级名称不能超过 100 个字符";
  return null;
}

export function validateGroupName(name: string, existingNames: string[] = []): string | null {
  const value = name.trim();
  if (!value) return "请输入小组名称";
  if (value.length > 100) return "小组名称不能超过 100 个字符";
  const lowered = value.toLowerCase();
  if (existingNames.some((item) => item.trim().toLowerCase() === lowered)) {
    return "小组名称不能重复";
  }
  return null;
}

export function validateInviteCode(value: string): string | null {
  const code = value.trim().toUpperCase();
  if (!code) return "请输入邀请码";
  if (!INVITE_CODE_REGEX.test(code)) return "邀请码格式无效";
  return null;
}

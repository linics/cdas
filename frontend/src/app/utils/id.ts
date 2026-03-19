export function generateId(prefix = "id"): string {
  const now = Date.now().toString(36);
  const random = Math.random().toString(36).slice(2, 8);
  return `${prefix}_${now}_${random}`;
}

export function nowIso(): string {
  return new Date().toISOString();
}

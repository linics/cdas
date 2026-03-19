const ALLOWED_EXTENSIONS = [".pdf", ".doc", ".docx"];
const MAX_FILE_BYTES = 10 * 1024 * 1024;

export function validateKnowledgeFile(file: File): string | null {
  const filename = file.name.toLowerCase();
  const hasAllowedExtension = ALLOWED_EXTENSIONS.some((extension) => filename.endsWith(extension));
  if (!hasAllowedExtension) return "仅支持上传 PDF、DOC 或 DOCX 文档";
  if (file.size <= 0) return "上传文档不能为空文件";
  if (file.size > MAX_FILE_BYTES) return "上传文档不能超过 10MB";
  return null;
}

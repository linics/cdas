type DocumentValidationTarget = "document" | "attachment";

const ALLOWED_EXTENSIONS = [".pdf", ".docx", ".txt"];
const MAX_FILE_BYTES = 10 * 1024 * 1024;

function validationNoun(target: DocumentValidationTarget): string {
  return target === "attachment" ? "附件" : "文档";
}

export function validateDocumentFile(file: File, target: DocumentValidationTarget = "document"): string | null {
  const filename = file.name.toLowerCase();
  const hasAllowedExtension = ALLOWED_EXTENSIONS.some((extension) => filename.endsWith(extension));
  if (!hasAllowedExtension) return `仅支持上传 PDF、DOCX 或 TXT ${validationNoun(target)}`;
  if (file.size <= 0) return `上传${validationNoun(target)}不能为空文件`;
  if (file.size > MAX_FILE_BYTES) return `上传${validationNoun(target)}不能超过 10MB`;
  return null;
}

export function validateKnowledgeFile(file: File): string | null {
  return validateDocumentFile(file, "document");
}

export function validateSubmissionAttachmentFile(file: File): string | null {
  return validateDocumentFile(file, "attachment");
}

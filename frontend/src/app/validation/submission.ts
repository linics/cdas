export interface SubmissionAttachmentInput {
  filename: string;
  url: string;
  type?: string;
  source?: "link" | "upload";
  parsing_status?: "uploaded" | "indexing" | "ready" | "failed";
  error_msg?: string | null;
}

export interface SubmissionValidationInput {
  contentText: string;
  attachments: SubmissionAttachmentInput[];
  checkpoints?: Record<string, boolean>;
}

export function isHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

export function validateAttachmentDraft(
  filename: string,
  url: string,
  existingAttachments: SubmissionAttachmentInput[] = [],
): string | null {
  const trimmedName = filename.trim();
  const trimmedUrl = url.trim();
  if (!trimmedName || !trimmedUrl) return "附件名称和链接都不能为空";
  if (!isHttpUrl(trimmedUrl)) return "附件链接必须为 http/https 地址";
  const duplicate = existingAttachments.some(
    (item) => item.filename.trim() === trimmedName && item.url.trim() === trimmedUrl,
  );
  if (duplicate) return "相同附件已存在，无需重复添加";
  return null;
}

export function validateSubmissionForSubmit(input: SubmissionValidationInput): string | null {
  if (
    input.attachments.some(
      (item) =>
        (item.source !== "upload" && (!item.filename.trim() || !item.url.trim() || !isHttpUrl(item.url.trim()))),
    )
  ) {
    return "存在无效附件，请先修正附件名称或链接";
  }
  const pendingUpload = input.attachments.find(
    (item) => item.source === "upload" && item.parsing_status && item.parsing_status !== "ready",
  );
  if (pendingUpload) {
    return pendingUpload.error_msg?.trim()
      ? `附件《${pendingUpload.filename}》尚未就绪：${pendingUpload.error_msg?.trim()}`
      : `附件《${pendingUpload.filename}》尚未就绪，请等待解析完成后再提交`;
  }
  const hasText = input.contentText.trim().length > 0;
  const hasAttachment = input.attachments.length > 0;
  const hasCheckpoint = Object.values(input.checkpoints || {}).some(Boolean);
  if (!hasText && !hasAttachment && !hasCheckpoint) {
    return "正式提交前至少需要一项证据（文本、附件或检查点）";
  }
  return null;
}

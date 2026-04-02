export type UserRole = "teacher" | "student";
export type SchoolStage = "primary" | "middle";
export type AssignmentType = "practical" | "inquiry" | "project";
export type InquiryDepth = "basic" | "intermediate" | "deep";
export type SubmissionMode = "phased" | "once" | "mixed";
export type SubmissionStatus = "draft" | "submitted" | "graded";
export type EvaluationType = "teacher" | "self" | "peer";
export type EvaluationLevel = "excellent" | "good" | "pass" | "improve";

const TOKEN_KEY = "cdas_token";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
  auth?: boolean;
  timeoutMs?: number;
};

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

function getApiBaseUrl(): string {
  return (import.meta.env.VITE_API_BASE_URL || "").trim();
}

function buildUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  const apiBaseUrl = getApiBaseUrl();
  if (!apiBaseUrl) return path;
  return `${apiBaseUrl}${path}`;
}

function withQuery(path: string, params: Record<string, unknown>): string {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    searchParams.set(key, String(value));
  });
  const query = searchParams.toString();
  return query ? `${path}?${query}` : path;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, auth = true, timeoutMs = 30000, headers, ...rest } = options;
  const requestHeaders = new Headers(headers || {});

  if (auth) {
    const token = getToken();
    if (token) {
      requestHeaders.set("Authorization", `Bearer ${token}`);
    }
  }

  let requestBody: BodyInit | undefined;
  if (body instanceof FormData) {
    requestBody = body;
  } else if (body instanceof URLSearchParams) {
    requestHeaders.set("Content-Type", "application/x-www-form-urlencoded");
    requestBody = body.toString();
  } else if (typeof body === "string") {
    requestBody = body;
  } else if (body !== undefined && body !== null) {
    requestHeaders.set("Content-Type", "application/json");
    requestBody = JSON.stringify(body);
  }

  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);

  let response: Response;
  try {
    response = await fetch(buildUrl(path), {
      ...rest,
      body: requestBody,
      headers: requestHeaders,
      signal: controller.signal,
    });
  } catch (error) {
    window.clearTimeout(timer);
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(0, "请求超时，请稍后重试");
    }
    throw new ApiError(0, "网络异常，请检查后端服务是否启动");
  }

  window.clearTimeout(timer);

  const contentType = response.headers.get("content-type") || "";
  let payload: unknown;
  if (response.status !== 204) {
    if (contentType.includes("application/json")) {
      payload = await response.json();
    } else {
      payload = await response.text();
    }
  }

  if (!response.ok) {
    if (response.status === 401) {
      clearToken();
      window.dispatchEvent(new Event("cdas-auth-invalid"));
    }

    const detail =
      typeof payload === "object" && payload && "detail" in payload
        ? (payload as { detail?: unknown }).detail
        : payload;
    const message =
      typeof detail === "string"
        ? detail
        : `请求失败（${response.status}）`;
    throw new ApiError(response.status, message, detail);
  }

  return payload as T;
}

function parseDownloadFilename(contentDisposition: string | null, fallbackFilename: string): string {
  if (!contentDisposition) {
    return fallbackFilename;
  }
  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }
  const quotedMatch = contentDisposition.match(/filename="([^"]+)"/i);
  if (quotedMatch?.[1]) {
    return quotedMatch[1];
  }
  const plainMatch = contentDisposition.match(/filename=([^;]+)/i);
  if (plainMatch?.[1]) {
    return plainMatch[1].trim();
  }
  return fallbackFilename;
}

export function normalizeAttachmentUrl(url: string): string {
  return buildUrl(url);
}

export async function downloadAuthenticatedFile(url: string, fallbackFilename: string): Promise<void> {
  const requestHeaders = new Headers();
  const token = getToken();
  if (token) {
    requestHeaders.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;
  try {
    response = await fetch(normalizeAttachmentUrl(url), {
      method: "GET",
      headers: requestHeaders,
    });
  } catch {
    throw new ApiError(0, "网络异常，请检查后端服务是否启动");
  }

  if (!response.ok) {
    if (response.status === 401) {
      clearToken();
      window.dispatchEvent(new Event("cdas-auth-invalid"));
    }
    const contentType = response.headers.get("content-type") || "";
    let detail: unknown = "";
    if (contentType.includes("application/json")) {
      const payload = await response.json().catch(() => null);
      detail = payload && typeof payload === "object" && "detail" in payload ? payload.detail : payload;
    } else {
      detail = await response.text().catch(() => "");
    }
    const message = typeof detail === "string" && detail ? detail : `请求失败（${response.status}）`;
    throw new ApiError(response.status, message, detail);
  }

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = parseDownloadFilename(response.headers.get("content-disposition"), fallbackFilename);
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

export interface ApiUser {
  id: number;
  username: string;
  role: UserRole;
  name: string;
  grade?: number | null;
  class_name?: string | null;
}

export interface AuthRegisterPayload {
  username: string;
  password: string;
  role: UserRole;
  name: string;
  grade?: number;
  class_name?: string;
}

export interface AuthLoginResponse {
  access_token: string;
  token_type: "bearer";
}

export interface Subject {
  id: number;
  code: string;
  name: string;
  category: string;
  primary_available: boolean;
  middle_available: boolean;
  grade_range?: string | null;
  core_competencies: Array<{ dimension: string; description: string }>;
}

export interface SubjectListResponse {
  subjects: Subject[];
  total: number;
}

export interface Classroom {
  id: number;
  name: string;
  grade: number;
  invite_code: string;
  teacher_id: number;
  teacher_name?: string | null;
  member_count: number;
  joined_group_id?: number | null;
  joined_group_name?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ClassroomListResponse {
  classes: Classroom[];
  total: number;
}

export interface ClassroomMember {
  member_id: number;
  student_id: number;
  student_name: string;
  student_username: string;
  student_grade?: number | null;
  student_class_name?: string | null;
  group_id?: number | null;
  group_name?: string | null;
  joined_at: string;
}

export interface ClassroomMemberListResponse {
  classroom: Classroom;
  members: ClassroomMember[];
  total: number;
}

export interface JoinClassResponse {
  classroom: Classroom;
  joined: boolean;
  message: string;
}

export interface ClassGroupMember {
  id: number;
  classroom_id: number;
  group_id: number;
  student_id: number;
  student_name: string;
  student_username: string;
  student_grade?: number | null;
  student_class_name?: string | null;
  assigned_at: string;
}

export interface ClassGroup {
  id: number;
  classroom_id: number;
  name: string;
  member_count: number;
  members?: ClassGroupMember[];
  created_at: string;
  updated_at: string;
}

export interface ClassGroupListResponse {
  classroom: Classroom;
  groups: ClassGroup[];
  total: number;
}

export interface AssignmentStep {
  name: string;
  description: string;
  checkpoints: Array<{ content: string; evidence_type: string }>;
  content?: string;
}

export interface AssignmentPhase {
  name: string;
  order: number;
  title?: string;
  steps: AssignmentStep[];
}

export interface AssignmentRubricDimension {
  name: string;
  levels?: Record<string, string>;
  description?: string;
  weight?: number;
}

export interface AIGenerationMeta {
  source: "ai" | "fallback" | "manual_merge";
  prompt_id: string;
  prompt_version: string;
  used_rag: boolean;
  fallback_reason: string;
  stage?: string;
  request_id?: string;
  warnings?: string[];
  input_truncated?: boolean;
  selected_chunk_ids?: string[];
  selected_document_ids?: number[];
  upstream_extract_source?: "ai" | "fallback" | "manual_merge" | string;
  upstream_extract_fallback_reason?: string;
}

export interface Assignment {
  id: number;
  title: string;
  topic: string;
  description?: string | null;
  school_stage: SchoolStage;
  grade: number;
  main_subject_id: number;
  related_subject_ids: number[];
  assignment_type: AssignmentType;
  practical_subtype?: "visit" | "simulation" | "observation" | null;
  inquiry_subtype?: "literature" | "survey" | "experiment" | null;
  inquiry_depth: InquiryDepth;
  submission_mode: SubmissionMode;
  duration_weeks: number;
  deadline?: string | null;
  objectives_json: Record<string, string>;
  phases_json: AssignmentPhase[];
  rubric_json: { dimensions?: AssignmentRubricDimension[] };
  is_published: boolean;
  is_archived?: boolean;
  archived_at?: string | null;
  created_by: number;
  document_id?: number | null;
  created_at: string;
}

export interface AssignmentCreatePayload {
  title: string;
  topic: string;
  description?: string;
  school_stage: SchoolStage;
  grade: number;
  main_subject_id: number;
  related_subject_ids: number[];
  document_id?: number | null;
  assignment_type: AssignmentType;
  practical_subtype?: "visit" | "simulation" | "observation";
  inquiry_subtype?: "literature" | "survey" | "experiment";
  inquiry_depth: InquiryDepth;
  submission_mode: SubmissionMode;
  duration_weeks: number;
  deadline?: string | null;
  objectives_json?: Record<string, string>;
  phases_json?: AssignmentPhase[];
  rubric_json?: { dimensions?: AssignmentRubricDimension[] };
}

export interface AssignmentUpdatePayload {
  title?: string;
  topic?: string;
  description?: string;
  document_id?: number | null;
  objectives_json?: Record<string, string>;
  phases_json?: AssignmentPhase[];
  rubric_json?: { dimensions?: AssignmentRubricDimension[] };
  deadline?: string | null;
}

export interface AssignmentListResponse {
  assignments: Assignment[];
  total: number;
}

export interface AssignmentPreviewResponse {
  objectives_json: Record<string, string>;
  phases_json: AssignmentPhase[];
  rubric_json: { dimensions?: AssignmentRubricDimension[] };
  meta?: AIGenerationMeta;
}

export interface AssignmentLessonPlanDraftRequest {
  document_id: number;
  title?: string;
  topic?: string;
  description?: string;
  background_setting?: string;
  school_stage?: SchoolStage;
  grade?: number;
  main_subject_id?: number | null;
  related_subject_ids?: number[];
  assignment_type?: AssignmentType;
  practical_subtype?: "visit" | "simulation" | "observation";
  inquiry_subtype?: "literature" | "survey" | "experiment";
  inquiry_depth?: InquiryDepth;
  submission_mode?: SubmissionMode;
  duration_weeks?: number;
}

export interface AssignmentLessonPlanDraftResponse {
  title: string;
  topic: string;
  description: string;
  school_stage: SchoolStage;
  grade: number;
  main_subject_id: number;
  related_subject_ids: number[];
  document_id: number;
  assignment_type: AssignmentType;
  practical_subtype?: "visit" | "simulation" | "observation" | null;
  inquiry_subtype?: "literature" | "survey" | "experiment" | null;
  inquiry_depth: InquiryDepth;
  submission_mode: SubmissionMode;
  duration_weeks: number;
  objectives_json: Record<string, string>;
  phases_json: AssignmentPhase[];
  rubric_json: { dimensions?: AssignmentRubricDimension[] };
  source_summary: string;
  meta?: AIGenerationMeta;
}

export interface AssignmentGroupMember {
  user_id: number;
  name?: string;
  username?: string;
  role?: string;
}

export interface AssignmentGroup {
  id: number;
  assignment_id: number;
  name: string;
  members_json: AssignmentGroupMember[];
}

export interface Submission {
  id: number;
  assignment_id: number;
  student_id: number;
  group_id?: number | null;
  group_name?: string | null;
  group_members?: AssignmentGroupMember[];
  phase_index: number;
  step_index?: number | null;
  status: SubmissionStatus;
  content_json: Record<string, unknown>;
  attachments_json: SubmissionAttachment[];
  checkpoints_json: Record<string, boolean>;
  created_at: string;
  submitted_at?: string | null;
  teacher_evaluated_at?: string | null;
  next_submission_id?: number | null;
  assignment?: {
    id: number;
    title: string;
    topic: string;
    description?: string | null;
    assignment_type: AssignmentType;
    phases_json: AssignmentPhase[];
  };
}

export interface SubmissionCreatePayload {
  assignment_id: number;
  phase_index: number;
  step_index?: number;
  group_id?: number;
  content_json?: Record<string, unknown>;
  attachments_json?: SubmissionLinkAttachmentInput[];
  checkpoints_json?: Record<string, boolean>;
}

export interface SubmissionUpdatePayload {
  content_json?: Record<string, unknown>;
  attachments_json?: SubmissionLinkAttachmentInput[];
  checkpoints_json?: Record<string, boolean>;
}

export interface SubmissionListResponse {
  submissions: Submission[];
  total: number;
}

export interface SubmissionAttachment {
  filename: string;
  url: string;
  type: string;
  size_bytes?: number;
  attachment_id?: number;
  source?: "link" | "upload";
  parsing_status?: "uploaded" | "indexing" | "ready" | "failed";
  mime_type?: string | null;
  error_msg?: string | null;
  summary_text?: string | null;
}

export interface SubmissionLinkAttachmentInput {
  filename: string;
  url: string;
  type: string;
  size_bytes?: number;
}

export interface SubmissionAttachmentListResponse {
  attachments: SubmissionAttachment[];
  total: number;
}

export interface Evaluation {
  id: number;
  submission_id: number;
  evaluator_id: number;
  evaluation_type: EvaluationType;
  score_level?: EvaluationLevel | null;
  score_numeric?: number | null;
  dimension_scores_json: Record<string, number>;
  score_level_label?: string | null;
  dimension_level_labels: Record<string, string>;
  feedback?: string | null;
  ai_generated: boolean;
  is_anonymous: boolean;
  created_at: string;
}

export interface EvaluationListResponse {
  evaluations: Evaluation[];
  total: number;
}

export interface TeacherEvaluationPayload {
  submission_id: number;
  score_numeric: number;
  score_level?: EvaluationLevel;
  dimension_scores_json: Record<string, number>;
  feedback: string;
}

export interface SelfEvaluationPayload {
  submission_id: number;
  completion: number;
  effort: number;
  difficulties?: string;
  gains?: string;
  improvement?: string;
}

export interface PeerEvaluationPayload {
  submission_id: number;
  quality: number;
  clarity: number;
  highlights?: string;
  suggestions?: string;
}

export interface AiAssistSuggestion {
  suggested_level?: string;
  suggested_score?: number;
  dimension_scores?: Record<string, number>;
  feedback?: string;
  evidence?: Array<{ source?: string; quote?: string; reason?: string }>;
  action_items?: string[];
}

export interface AiAssistResponse {
  message: string;
  suggestion: AiAssistSuggestion;
  meta?: AIGenerationMeta;
}

export type DocumentStatus = "uploaded" | "indexing" | "ready" | "failed";

export interface DocumentItem {
  id: number;
  filename: string;
  status?: DocumentStatus;
  parsing_status?: DocumentStatus;
  upload_date: string;
  metadata_json?: Record<string, unknown>;
  source?: "user" | "system";
  error_msg?: string | null;
}

export interface DocumentUploadResponse {
  document_id: number;
  filename: string;
  status?: DocumentStatus;
  parsing_status?: DocumentStatus;
}

export const authApi = {
  register: (payload: AuthRegisterPayload) =>
    request<ApiUser>("/api/v2/auth/register", {
      method: "POST",
      auth: false,
      body: payload,
    }),

  login: (username: string, password: string, role?: UserRole) => {
    const form = new URLSearchParams();
    form.set("username", username);
    form.set("password", password);
    if (role) {
      form.set("role", role);
    }
    return request<AuthLoginResponse>("/api/v2/auth/login", {
      method: "POST",
      auth: false,
      body: form,
    });
  },

  getMe: () => request<ApiUser>("/api/v2/auth/me"),
};

export const subjectsApi = {
  list: (stage?: SchoolStage, category?: string) =>
    request<SubjectListResponse>(
      withQuery("/api/v2/subjects/", {
        stage,
        category,
      }),
    ),

  getById: (id: number) => request<Subject>(`/api/v2/subjects/${id}`),
};

export const classesApi = {
  create: (payload: { name: string; grade: number }) =>
    request<Classroom>("/api/v2/classes/", {
      method: "POST",
      body: payload,
    }),

  listMy: () => request<ClassroomListResponse>("/api/v2/classes/my"),

  join: (inviteCode: string) =>
    request<JoinClassResponse>("/api/v2/classes/join", {
      method: "POST",
      body: {
        invite_code: inviteCode,
      },
    }),

  listMembers: (classId: number) =>
    request<ClassroomMemberListResponse>(`/api/v2/classes/${classId}/members`),

  listGroups: (classId: number) =>
    request<ClassGroupListResponse>(`/api/v2/classes/${classId}/groups`),

  createGroup: (classId: number, name: string) =>
    request<ClassGroup>(`/api/v2/classes/${classId}/groups`, {
      method: "POST",
      body: {
        name,
      },
    }),

  assignGroupMember: (classId: number, groupId: number, studentId: number) =>
    request<ClassGroup>(`/api/v2/classes/${classId}/groups/${groupId}/members`, {
      method: "POST",
      body: {
        student_id: studentId,
      },
    }),

  removeGroupMember: (classId: number, groupId: number, studentId: number) =>
    request<ClassGroup>(`/api/v2/classes/${classId}/groups/${groupId}/members/${studentId}`, {
      method: "DELETE",
    }),

  deleteGroup: (classId: number, groupId: number) =>
    request<void>(`/api/v2/classes/${classId}/groups/${groupId}`, {
      method: "DELETE",
    }),

  resetInviteCode: (classId: number) =>
    request<Classroom>(`/api/v2/classes/${classId}/invite-code/reset`, {
      method: "POST",
    }),
};

export const assignmentsApi = {
  preview: (payload: AssignmentCreatePayload, options?: { forceGenerate?: boolean }) =>
    request<AssignmentPreviewResponse>(
      withQuery("/api/v2/assignments/preview", {
        force_generate: options?.forceGenerate ?? true,
      }),
      {
      method: "POST",
      body: payload,
      },
    ),

  fromLessonPlan: (payload: AssignmentLessonPlanDraftRequest) =>
    request<AssignmentLessonPlanDraftResponse>("/api/v2/assignments/from-lesson-plan", {
      method: "POST",
      body: payload,
      timeoutMs: 90000,
    }),

  create: (payload: AssignmentCreatePayload) =>
    request<Assignment>("/api/v2/assignments/", {
      method: "POST",
      body: payload,
    }),

  list: (page = 1, pageSize = 20, publishedOnly = false, includeArchived = false) =>
    request<AssignmentListResponse>(
      withQuery("/api/v2/assignments/", {
        page,
        page_size: pageSize,
        published_only: publishedOnly,
        include_archived: includeArchived,
      }),
    ),

  getById: (id: number) => request<Assignment>(`/api/v2/assignments/${id}`),

  update: (id: number, payload: AssignmentUpdatePayload) =>
    request<Assignment>(`/api/v2/assignments/${id}`, {
      method: "PUT",
      body: payload,
    }),

  publish: (id: number) =>
    request<Assignment>(`/api/v2/assignments/${id}/publish`, {
      method: "POST",
    }),

  archive: (id: number) =>
    request<Assignment>(`/api/v2/assignments/${id}/archive`, {
      method: "POST",
    }),

  unarchive: (id: number) =>
    request<Assignment>(`/api/v2/assignments/${id}/unarchive`, {
      method: "POST",
    }),

  delete: (id: number) =>
    request<void>(`/api/v2/assignments/${id}`, {
      method: "DELETE",
    }),

  generateSteps: (id: number) =>
    request<{ message: string; phases: AssignmentPhase[] }>(
      `/api/v2/assignments/${id}/generate-steps`,
      {
        method: "POST",
      },
    ),

  createGroup: (id: number, payload: { name: string; members_json: AssignmentGroupMember[] }) =>
    request<AssignmentGroup>(`/api/v2/assignments/${id}/groups`, {
      method: "POST",
      body: payload,
    }),

  updateGroupMembers: (id: number, groupId: number, members: AssignmentGroupMember[]) =>
    request<AssignmentGroup>(`/api/v2/assignments/${id}/groups/${groupId}/members`, {
      method: "PUT",
      body: {
        members_json: members,
      },
    }),

  deleteGroup: (id: number, groupId: number) =>
    request<void>(`/api/v2/assignments/${id}/groups/${groupId}`, {
      method: "DELETE",
    }),

  listGroups: (id: number) =>
    request<AssignmentGroup[]>(`/api/v2/assignments/${id}/groups`),
};

export const submissionsApi = {
  create: (payload: SubmissionCreatePayload) =>
    request<Submission>("/api/v2/submissions/", {
      method: "POST",
      body: payload,
    }),

  listMy: (assignmentId?: number) =>
    request<SubmissionListResponse>(
      withQuery("/api/v2/submissions/my", {
        assignment_id: assignmentId,
      }),
    ),

  getById: (id: number) => request<Submission>(`/api/v2/submissions/${id}`),

  update: (id: number, payload: SubmissionUpdatePayload) =>
    request<Submission>(`/api/v2/submissions/${id}`, {
      method: "PUT",
      body: payload,
    }),

  uploadAttachment: (submissionId: number, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return request<SubmissionAttachment>(`/api/v2/submissions/${submissionId}/attachments/upload`, {
      method: "POST",
      body: formData,
    });
  },

  listAttachments: (submissionId: number) =>
    request<SubmissionAttachmentListResponse>(`/api/v2/submissions/${submissionId}/attachments`),

  deleteAttachment: (submissionId: number, attachmentId: number) =>
    request<void>(`/api/v2/submissions/${submissionId}/attachments/${attachmentId}`, {
      method: "DELETE",
    }),

  downloadAttachment: (attachment: SubmissionAttachment) =>
    downloadAuthenticatedFile(attachment.url, attachment.filename),

  submit: (id: number) =>
    request<Submission>(`/api/v2/submissions/${id}/submit`, {
      method: "POST",
    }),

  delete: (id: number) =>
    request<void>(`/api/v2/submissions/${id}`, {
      method: "DELETE",
    }),

  listByAssignment: (assignmentId: number, phaseIndex?: number, groupId?: number) =>
    request<SubmissionListResponse>(
      withQuery(`/api/v2/submissions/assignment/${assignmentId}`, {
        phase_index: phaseIndex,
        group_id: groupId,
      }),
    ),
};

export const evaluationsApi = {
  createTeacher: (payload: TeacherEvaluationPayload) =>
    request<Evaluation>("/api/v2/evaluations/teacher", {
      method: "POST",
      body: payload,
    }),

  createSelf: (payload: SelfEvaluationPayload) =>
    request<Evaluation>("/api/v2/evaluations/self", {
      method: "POST",
      body: payload,
    }),

  createPeer: (payload: PeerEvaluationPayload) =>
    request<Evaluation>("/api/v2/evaluations/peer", {
      method: "POST",
      body: payload,
    }),

  listBySubmission: (submissionId: number) =>
    request<EvaluationListResponse>(`/api/v2/evaluations/submission/${submissionId}`),

  aiAssist: (submissionId: number) =>
    request<AiAssistResponse>(
      withQuery("/api/v2/evaluations/ai-assist", {
        submission_id: submissionId,
      }),
      {
        method: "POST",
      },
    ),

  listMyReceived: () => request<EvaluationListResponse>("/api/v2/evaluations/my-received"),
};

export const documentsApi = {
  list: () => request<DocumentItem[]>("/api/documents"),

  upload: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return request<DocumentUploadResponse>("/api/documents/upload", {
      method: "POST",
      body: formData,
    });
  },

  getById: (id: number) => request<DocumentItem>(`/api/documents/${id}`),

  delete: (id: number) =>
    request<{ status: "deleted" }>(`/api/documents/${id}`, {
      method: "DELETE",
    }),
};

export function getApiErrorMessage(error: unknown, fallback = "操作失败，请稍后重试"): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}

import type { LessonStep, SchoolLevel } from "../data/models";

export interface AiDesignInput {
  schoolLevel: SchoolLevel;
  gradeName: string;
  title: string;
  description: string;
  mainSubjectName: string;
  integratedSubjectNames: string[];
  assignmentTypeName: string;
  depthName: string;
  crossConceptNames: string[];
  detailedSteps: LessonStep[];
}

export interface AiDraftSuggestion {
  title: string;
  description: string;
  detailedSteps: LessonStep[];
}

export interface AiRefineSuggestion {
  detailedSteps: LessonStep[];
}

export type AiErrorCode =
  | "BAD_REQUEST"
  | "UNAUTHORIZED"
  | "RATE_LIMIT"
  | "SERVER_ERROR"
  | "NETWORK_ERROR"
  | "PARSE_ERROR"
  | "UNKNOWN";

export interface AiServiceError {
  code: AiErrorCode;
  message: string;
  status?: number;
}

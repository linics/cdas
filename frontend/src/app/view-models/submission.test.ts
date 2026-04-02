import { describe, expect, it } from "vitest";

import type { AssignmentGroup, Submission, SubmissionAttachment } from "../lib/api";
import {
  buildSubmissionEditorState,
  buildGroupProgressRows,
  buildGroupScoreSummary,
  mergeSubmissionAttachment,
  patchSubmissionAttachments,
  preserveSubmissionEditorContent,
  removeSubmissionAttachment,
} from "./submission";

function makeGroup(overrides: Partial<AssignmentGroup> = {}): AssignmentGroup {
  return {
    id: 1,
    assignment_id: 101,
    name: "第一组",
    members_json: [],
    ...overrides,
  };
}

function makeSubmission(overrides: Partial<Submission> = {}): Submission {
  return {
    id: 1,
    assignment_id: 101,
    student_id: 501,
    phase_index: 0,
    status: "submitted",
    content_json: {},
    attachments_json: [],
    checkpoints_json: {},
    created_at: "2026-03-27T10:00:00Z",
    submitted_at: "2026-03-27T10:10:00Z",
    ...overrides,
  };
}

function makeAttachment(overrides: Partial<SubmissionAttachment> = {}): SubmissionAttachment {
  return {
    filename: "evidence.txt",
    url: "/api/v2/submissions/1/attachments/1/download",
    type: "txt",
    source: "upload",
    attachment_id: 1,
    parsing_status: "ready",
    ...overrides,
  };
}

describe("submission view models", () => {
  it("does not preseed empty group rows by default", () => {
    const rows = buildGroupProgressRows({
      groups: [makeGroup()],
      submissions: [],
      totalPhases: 2,
      includeUngrouped: true,
    });

    expect(rows).toEqual([]);
  });

  it("can preseed empty group rows when explicitly requested", () => {
    const rows = buildGroupProgressRows({
      groups: [makeGroup()],
      submissions: [],
      totalPhases: 2,
      preseedGroups: true,
    });

    expect(rows).toHaveLength(1);
    expect(rows[0]?.groupId).toBe(1);
    expect(rows[0]?.totalSubmissions).toBe(0);
  });

  it("does not create an ungrouped bucket when there are no personal submissions", () => {
    const rows = buildGroupProgressRows({
      groups: [makeGroup()],
      submissions: [
        makeSubmission({
          group_id: 1,
          group_name: "第一组",
        }),
      ],
      totalPhases: 2,
      includeUngrouped: true,
    });

    expect(rows.some((row) => row.groupId === null)).toBe(false);
    expect(buildGroupScoreSummary(rows).totalBuckets).toBe(1);
  });

  it("creates exactly one ungrouped bucket when personal submissions exist", () => {
    const rows = buildGroupProgressRows({
      groups: [makeGroup()],
      submissions: [
        makeSubmission({
          id: 1,
          group_id: 1,
          group_name: "第一组",
        }),
        makeSubmission({
          id: 2,
          student_id: 502,
          group_id: null,
          group_name: null,
        }),
      ],
      totalPhases: 2,
      includeUngrouped: true,
    });

    const ungroupedRows = rows.filter((row) => row.groupId === null);
    expect(ungroupedRows).toHaveLength(1);
    expect(ungroupedRows[0]?.label).toBe("个人提交");
    expect(ungroupedRows[0]?.totalSubmissions).toBe(1);
    expect(buildGroupScoreSummary(rows).totalBuckets).toBe(2);
  });

  it("prefers highest phase when requested for latest submission", () => {
    const rows = buildGroupProgressRows({
      groups: [makeGroup()],
      submissions: [
        makeSubmission({
          id: 1,
          group_id: 1,
          group_name: "第一组",
          phase_index: 1,
          created_at: "2026-03-27T10:00:00Z",
          submitted_at: "2026-03-27T10:10:00Z",
        }),
        makeSubmission({
          id: 2,
          group_id: 1,
          group_name: "第一组",
          phase_index: 0,
          created_at: "2026-03-27T12:00:00Z",
          submitted_at: "2026-03-27T12:10:00Z",
        }),
      ],
      totalPhases: 3,
      preseedGroups: true,
      latestSubmissionStrategy: "highest_phase_then_time",
    });

    expect(rows[0]?.latestSubmission?.id).toBe(1);
    expect(rows[0]?.phaseProgress).toBe("2/3");
  });

  it("keeps timestamp ordering when using latest_timestamp strategy", () => {
    const rows = buildGroupProgressRows({
      groups: [makeGroup()],
      submissions: [
        makeSubmission({
          id: 1,
          group_id: 1,
          group_name: "第一组",
          phase_index: 1,
          created_at: "2026-03-27T10:00:00Z",
          submitted_at: "2026-03-27T10:10:00Z",
        }),
        makeSubmission({
          id: 2,
          group_id: 1,
          group_name: "第一组",
          phase_index: 0,
          created_at: "2026-03-27T12:00:00Z",
          submitted_at: "2026-03-27T12:10:00Z",
        }),
      ],
      totalPhases: 3,
      preseedGroups: true,
      latestSubmissionStrategy: "latest_timestamp",
    });

    expect(rows[0]?.latestSubmission?.id).toBe(2);
  });

  it("merges uploaded attachment without dropping existing local attachments", () => {
    const next = mergeSubmissionAttachment(
      [
        {
          filename: "link",
          url: "https://example.com",
          type: "link",
          source: "link",
        },
      ],
      makeAttachment(),
    );

    expect(next).toHaveLength(2);
    expect(next[0]?.source).toBe("link");
    expect(next[1]?.attachment_id).toBe(1);
  });

  it("removes only the targeted uploaded attachment", () => {
    const remaining = removeSubmissionAttachment(
      [
        makeAttachment(),
        makeAttachment({
          attachment_id: 2,
          filename: "notes.txt",
          url: "/api/v2/submissions/1/attachments/2/download",
        }),
      ],
      {
        attachment_id: 1,
        filename: "evidence.txt",
        url: "/api/v2/submissions/1/attachments/1/download",
        source: "upload",
      },
    );

    expect(remaining).toHaveLength(1);
    expect(remaining[0]?.attachment_id).toBe(2);
  });

  it("patches submission attachments for the active draft only", () => {
    const patched = patchSubmissionAttachments(
      [
        makeSubmission({
          id: 1,
          attachments_json: [
            {
              filename: "link",
              url: "https://example.com",
              type: "link",
              source: "link",
            },
          ],
        }),
        makeSubmission({ id: 2 }),
      ],
      1,
      [
        {
          filename: "link",
          url: "https://example.com",
          type: "link",
          source: "link",
        },
        makeAttachment(),
      ],
    );

    expect(patched[0]?.attachments_json).toHaveLength(2);
    expect(patched[1]?.attachments_json).toEqual([]);
  });

  it("builds editor state from the latest server submission payload", () => {
    const editorState = buildSubmissionEditorState(
      makeSubmission({
        id: 1,
        content_json: { text: "服务端最新正文" },
        attachments_json: [
          {
            filename: "updated.txt",
            url: "/api/v2/submissions/1/attachments/2/download",
            type: "txt",
            source: "upload",
            attachment_id: 2,
            parsing_status: "ready",
          },
        ],
      }),
    );

    expect(editorState.contentText).toBe("服务端最新正文");
    expect(editorState.attachments).toHaveLength(1);
    expect(editorState.attachments[0]?.attachment_id).toBe(2);
  });

  it("preserves unsaved content when only local attachments change", () => {
    const editorState = preserveSubmissionEditorContent("还没保存的正文", [
      {
        filename: "link",
        url: "https://example.com",
        type: "link",
        source: "link",
      },
      makeAttachment(),
    ]);

    expect(editorState.contentText).toBe("还没保存的正文");
    expect(editorState.attachments).toHaveLength(2);
    expect(editorState.attachments[1]?.attachment_id).toBe(1);
  });
});

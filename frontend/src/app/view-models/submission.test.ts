import { describe, expect, it } from "vitest";

import type { AssignmentGroup, Submission } from "../lib/api";
import { buildGroupProgressRows, buildGroupScoreSummary } from "./submission";

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
});

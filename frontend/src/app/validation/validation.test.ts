import { describe, expect, it } from "vitest";

import { validateAssignmentDesignerForm } from "./assignment";
import { validateRegisterInput } from "./auth";
import { validateClassroomName, validateGroupName, validateInviteCode } from "./classroom";
import { validateTeacherEvaluation } from "./evaluation";
import { validateKnowledgeFile } from "./knowledge";
import { validateAttachmentDraft, validateSubmissionForSubmit } from "./submission";

describe("validation rules", () => {
  it("rejects assignment publish without enough rubric dimensions", () => {
    expect(
      validateAssignmentDesignerForm(
        {
          title: "校园节水行动",
          topic: "校园节水行动",
          school_stage: "middle",
          grade: 7,
          main_subject_id: 1,
          related_subject_ids: [],
          rubric_dimensions: ["问题意识"],
          steps: [
            { phaseName: "阶段一", stepName: "步骤一", description: "说明", evidence: "文本" },
            { phaseName: "阶段二", stepName: "步骤二", description: "说明", evidence: "文档" },
          ],
        },
        "publish",
      ),
    ).toBe("至少配置 2 个评价维度");
  });

  it("requires student grade during register", () => {
    expect(
      validateRegisterInput({
        role: "student",
        name: "小明",
        identifier: "student_1",
        password: "Passw0rd123",
      }),
    ).toBe("学生年级需在 1-9 之间");
  });

  it("rejects duplicate group names", () => {
    expect(validateGroupName("一组", ["一组", "二组"])).toBe("小组名称不能重复");
  });

  it("requires exact rubric dimensions in teacher evaluation", () => {
    expect(
      validateTeacherEvaluation({
        rubricDimensions: ["问题意识", "证据质量"],
        dimensionScores: { 问题意识: 3 },
        feedback: "整体表现不错",
      }),
    ).toBe("评分维度必须与量规维度完全一致");
  });

  it("requires evidence before final submission", () => {
    expect(validateSubmissionForSubmit({ contentText: "", attachments: [], checkpoints: {} })).toBe(
      "正式提交前至少需要一项证据（文本、附件或检查点）",
    );
  });

  it("rejects invalid attachment url", () => {
    expect(validateAttachmentDraft("附件", "ftp://bad.example.com")).toBe("附件链接必须为 http/https 地址");
  });

  it("validates invite code and class name", () => {
    expect(validateInviteCode("123")).toBe("邀请码格式无效");
    expect(validateClassroomName("   ")).toBe("请输入班级名称");
  });

  it("validates knowledge file extension and size", () => {
    const badType = new File(["hi"], "demo.txt", { type: "text/plain" });
    const bigFile = new File([new Uint8Array(10 * 1024 * 1024 + 1)], "demo.docx");
    expect(validateKnowledgeFile(badType)).toBe("仅支持上传 PDF、DOC 或 DOCX 文档");
    expect(validateKnowledgeFile(bigFile)).toBe("上传文档不能超过 10MB");
  });
});

import { Document, Packer, Paragraph, TextRun, HeadingLevel } from "docx";
import { saveAs } from "file-saver";
import html2canvas from "html2canvas";
import jsPDF from "jspdf";
import { ASSIGNMENT_TYPES, CROSS_CONCEPTS, DEPTH_LEVELS, GRADES, SUBJECTS } from "../data/constants";
import { LESSON_PLAN_BASE_TEXT } from "../data/lessonPlanTemplate";
import type { AssignmentDraft, ClassRoom, LessonPlanDocument, LessonSection, LessonStep } from "../data/models";

function nameById<T extends { id: string; name: string }>(list: T[], id: string): string {
  return list.find((item) => item.id === id)?.name ?? id;
}

function formatDate(date = new Date()): string {
  const yyyy = date.getFullYear();
  const mm = `${date.getMonth() + 1}`.padStart(2, "0");
  const dd = `${date.getDate()}`.padStart(2, "0");
  return `${yyyy}${mm}${dd}`;
}

function sanitizeFileName(input: string): string {
  return input.replace(/[\\/:*?"<>|]/g, "_").slice(0, 80);
}

function renderTaskTableText(steps: LessonStep[]): string {
  return steps
    .map((step, index) => {
      return [
        `任务 ${index + 1}: ${step.phaseName} - ${step.stepName}`,
        `学习活动: ${step.studentActivity}`,
        `教师支持: ${step.teacherActivity}`,
        `学习支持: ${step.learningSupport}`,
        `学习成果: ${step.evidence}`,
        "",
      ].join("\n");
    })
    .join("\n");
}

function renderEvaluationText(steps: LessonStep[]): string {
  return steps
    .map((step, index) => `${index + 1}. ${step.stepName}: ${step.evaluationPoints}`)
    .join("\n");
}

function renderPeriodText(steps: LessonStep[]): string {
  return steps
    .map((step, index) => {
      return [
        `第${index + 1}课时：${step.stepName}`,
        `目标：${step.learningGoal}`,
        `教师活动：${step.teacherActivity}`,
        `学生活动：${step.studentActivity}`,
        `建议时长：${step.lessonTimeSuggestion}`,
        "",
      ].join("\n");
    })
    .join("\n");
}

export function buildLessonPlan(
  assignment: AssignmentDraft,
  targetClasses: ClassRoom[],
  teacherName: string,
): LessonPlanDocument {
  const mainSubjectName = nameById(SUBJECTS, assignment.mainSubject);
  const integratedNames = assignment.integratedSubjects.map((id) => nameById(SUBJECTS, id)).join("、") || "暂无";
  const crossConceptNames = assignment.crossConcepts.map((id) => nameById(CROSS_CONCEPTS, id)).join("、") || "暂无";
  const gradeName = nameById(GRADES, assignment.grade);
  const assignmentTypeName = nameById(ASSIGNMENT_TYPES, assignment.type);
  const depthName = nameById(DEPTH_LEVELS, assignment.depth);
  const classNames = targetClasses.map((c) => c.name).join("、") || "未发布班级";

  const sections: LessonSection[] = [
    {
      title: "一、基本信息",
      content: [
        `主题名称：${assignment.title}`,
        `适用年级：${gradeName}`,
        `学段：${assignment.schoolLevel}`,
        `主要学科：${mainSubjectName}`,
        `关联学科：${integratedNames}`,
        `跨学科概念：${crossConceptNames}`,
        `作业类型：${assignmentTypeName}`,
        `探究深度：${depthName}`,
        `发布班级：${classNames}`,
        `设计者：${teacherName}`,
      ].join("\n"),
    },
    {
      title: "二、跨学科主题学习的教学设计",
      content: [
        `教学设计简介：${assignment.description || LESSON_PLAN_BASE_TEXT.designIntro}`,
        `设计依据：${LESSON_PLAN_BASE_TEXT.designBasis}`,
      ].join("\n\n"),
    },
    {
      title: "三、学习目标",
      content: assignment.detailedSteps
        .map((step, index) => `${index + 1}. ${step.learningGoal}`)
        .join("\n"),
    },
    {
      title: "四、组织架构与任务链",
      content: [
        LESSON_PLAN_BASE_TEXT.organization,
        "",
        "任务链：",
        ...assignment.detailedSteps.map((step, index) => `${index + 1}. ${step.phaseName} - ${step.stepName}`),
      ].join("\n"),
    },
    {
      title: "五、学习组织方式",
      content:
        "采用4-6人小组协作，课堂与场域联动推进；教师负责过程支架，学生负责证据采集、分析与展示。",
    },
    {
      title: "六、学习任务—学习活动—学习支持—学习成果",
      content: renderTaskTableText(assignment.detailedSteps),
    },
    {
      title: "七、评价设计",
      content: [LESSON_PLAN_BASE_TEXT.evaluation, "", renderEvaluationText(assignment.detailedSteps)].join("\n"),
    },
    {
      title: "八、课时设计",
      content: renderPeriodText(assignment.detailedSteps),
    },
    {
      title: "九、学习资源与技术手段建议",
      content: LESSON_PLAN_BASE_TEXT.resource,
    },
    {
      title: "十、教学特色与反思",
      content: LESSON_PLAN_BASE_TEXT.reflection,
    },
  ];

  return {
    assignmentId: assignment.id,
    title: assignment.title,
    sections,
    generatedAt: new Date().toISOString(),
  };
}

export function lessonPlanToPlainText(doc: LessonPlanDocument): string {
  return doc.sections.map((section) => `${section.title}\n${section.content}`).join("\n\n");
}

export async function downloadLessonPlanWord(doc: LessonPlanDocument): Promise<void> {
  const children: Paragraph[] = [];

  children.push(
    new Paragraph({
      heading: HeadingLevel.TITLE,
      children: [new TextRun({ text: `${doc.title} 教学设计教案`, bold: true })],
    }),
  );

  doc.sections.forEach((section) => {
    children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, text: section.title }));
    section.content.split("\n").forEach((line) => {
      children.push(new Paragraph({ text: line || " " }));
    });
    children.push(new Paragraph({ text: " " }));
  });

  const document = new Document({
    sections: [{ children }],
  });

  const blob = await Packer.toBlob(document);
  const fileName = `跨学科教案_${sanitizeFileName(doc.title)}_${formatDate()}.docx`;
  saveAs(blob, fileName);
}

export async function downloadLessonPlanPdf(doc: LessonPlanDocument): Promise<void> {
  const text = lessonPlanToPlainText(doc);

  const container = document.createElement("div");
  container.style.position = "fixed";
  container.style.left = "-10000px";
  container.style.top = "0";
  container.style.width = "794px";
  container.style.padding = "40px";
  container.style.background = "#ffffff";
  container.style.color = "#111827";
  container.style.fontSize = "14px";
  container.style.lineHeight = "1.8";
  container.style.whiteSpace = "pre-wrap";
  container.style.wordBreak = "break-word";
  container.textContent = `${doc.title} 教学设计教案\n\n${text}`;

  document.body.appendChild(container);

  const canvas = await html2canvas(container, {
    backgroundColor: "#ffffff",
    scale: 2,
    useCORS: true,
  });

  document.body.removeChild(container);

  const pdf = new jsPDF("p", "mm", "a4");
  const pageWidth = 210;
  const pageHeight = 297;

  const imgWidth = pageWidth;
  const imgHeight = (canvas.height * imgWidth) / canvas.width;

  let heightLeft = imgHeight;
  let position = 0;

  const imgData = canvas.toDataURL("image/png");
  pdf.addImage(imgData, "PNG", 0, position, imgWidth, imgHeight);
  heightLeft -= pageHeight;

  while (heightLeft > 0) {
    position = heightLeft - imgHeight;
    pdf.addPage();
    pdf.addImage(imgData, "PNG", 0, position, imgWidth, imgHeight);
    heightLeft -= pageHeight;
  }

  const fileName = `跨学科教案_${sanitizeFileName(doc.title)}_${formatDate()}.pdf`;
  pdf.save(fileName);
}

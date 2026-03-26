import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { Archive, CheckCircle2, FileText, PlusCircle, Users } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { PageState } from "../components/PageState";
import { StatusBanner } from "../components/StatusBanner";
import {
  assignmentsApi,
  getApiErrorMessage,
  type Assignment,
  subjectsApi,
  type Subject,
} from "../lib/api";
import { stageToSchoolLevel } from "../lib/mappers";

function gradeLabel(grade: number): string {
  if (grade >= 1 && grade <= 6) return `小学${grade}年级`;
  return `初中${Math.max(1, grade - 6)}年级`;
}

export function Dashboard() {
  const { user } = useAuth();
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadToken, setReloadToken] = useState(0);

  const retryLoad = () => {
    setReloadToken((value) => value + 1);
  };

  useEffect(() => {
    let mounted = true;

    async function loadData() {
      if (!user || user.role !== "teacher") {
        if (mounted) setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setError("");
      try {
        const [assignmentResp, subjectResp] = await Promise.all([
          assignmentsApi.list(1, 100, false, true),
          subjectsApi.list(),
        ]);
        if (!mounted) return;
        setAssignments(assignmentResp.assignments || []);
        setSubjects(subjectResp.subjects || []);
      } catch (err) {
        if (!mounted) return;
        setError(getApiErrorMessage(err, "加载作业数据失败"));
      } finally {
        if (mounted) setIsLoading(false);
      }
    }

    loadData();
    return () => {
      mounted = false;
    };
  }, [user, reloadToken]);

  const subjectById = useMemo(() => {
    const map = new Map<number, Subject>();
    subjects.forEach((subject) => {
      map.set(subject.id, subject);
    });
    return map;
  }, [subjects]);

  const sortedAssignments = useMemo(
    () => [...assignments].sort((a, b) => (a.created_at < b.created_at ? 1 : -1)),
    [assignments],
  );

  const draftCount = assignments.filter((item) => !item.is_published && !item.is_archived).length;
  const publishedCount = assignments.filter((item) => item.is_published && !item.is_archived).length;
  const archivedCount = assignments.filter((item) => Boolean(item.is_archived)).length;
  const latest = sortedAssignments.filter((item) => !item.is_archived).slice(0, 5);

  if (!user || user.role !== "teacher") {
    return <PageState variant="warning" title="访问受限" description="当前账号不是教师身份。" actionLabel="切换到学生首页" actionTo="/student" />;
  }

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      <section className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-text">欢迎回来，{user.name}</h1>
          <p className="text-sm text-text-secondary mt-1">
            你当前创建了 <span className="font-bold text-primary">{assignments.length}</span> 份跨学科作业。
          </p>
        </div>
        <Link
          to="/create"
          className="inline-flex items-center gap-2 bg-primary text-white px-6 py-3 rounded-xl font-bold hover:bg-primary-hover active:bg-primary-active"
        >
          <PlusCircle className="w-5 h-5" /> 设计新作业
        </Link>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-surface rounded-2xl border border-border p-5 space-y-2">
          <div className="w-8 h-8 rounded-lg bg-warning-soft text-warning flex items-center justify-center">
            <FileText className="w-4 h-4" />
          </div>
          <p className="text-xs text-text-secondary">草稿作业</p>
          <p className="text-2xl font-black text-warning">{draftCount}</p>
        </div>
        <div className="bg-surface rounded-2xl border border-border p-5 space-y-2">
          <div className="w-8 h-8 rounded-lg bg-success-soft text-success flex items-center justify-center">
            <CheckCircle2 className="w-4 h-4" />
          </div>
          <p className="text-xs text-text-secondary">已发布作业</p>
          <p className="text-2xl font-black text-success">{publishedCount}</p>
        </div>
        <div className="bg-surface rounded-2xl border border-border p-5 space-y-2">
          <div className="w-8 h-8 rounded-lg bg-secondary text-text-secondary flex items-center justify-center">
            <Archive className="w-4 h-4" />
          </div>
          <p className="text-xs text-text-secondary">已归档作业</p>
          <p className="text-2xl font-black text-text">{archivedCount}</p>
        </div>
        <div className="bg-surface rounded-2xl border border-border p-5 space-y-2">
          <div className="w-8 h-8 rounded-lg bg-secondary text-primary flex items-center justify-center">
            <Users className="w-4 h-4" />
          </div>
          <p className="text-xs text-text-secondary">班级管理</p>
          <p className="text-base font-black text-primary">已接入</p>
          <p className="text-[11px] text-text-muted">支持创建班级、发放邀请码、入班与班级分组</p>
        </div>
      </section>

      <section className="bg-surface rounded-2xl border border-border p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold">最近更新的作业</h2>
          <Link to="/create" className="text-sm font-semibold text-primary hover:underline">
            进入设计器
          </Link>
        </div>

        {isLoading && <p className="text-sm text-text-secondary">加载中...</p>}
        {!isLoading && error && (
          <StatusBanner tone="error" message={error} actionLabel="重试加载" onAction={retryLoad} />
        )}
        {!isLoading && !error && latest.length === 0 && (
          <p className="text-sm text-text-secondary">暂无作业，请先创建。</p>
        )}

        <div className="space-y-3">
          {latest.map((assignment) => {
            const mainSubjectName = subjectById.get(assignment.main_subject_id)?.name || "未匹配学科";
            return (
              <div
                key={assignment.id}
                className="p-4 bg-surface-muted border border-border rounded-xl flex items-center justify-between gap-4"
              >
                <div>
                  <p className="font-semibold">{assignment.title}</p>
                  <p className="text-xs text-text-secondary mt-1">
                    {stageToSchoolLevel(assignment.school_stage)} · {gradeLabel(assignment.grade)} · 主学科：
                    {mainSubjectName}
                  </p>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <span className="px-2 py-1 rounded-full bg-secondary text-text">
                    {assignment.is_archived ? "已归档" : assignment.is_published ? "已发布" : "草稿"}
                  </span>
                  <Link
                    to={`/assignment/${assignment.id}`}
                    className="text-text-secondary font-semibold hover:underline"
                  >
                    查看提交
                  </Link>
                  <Link
                    to={`/create?edit=${assignment.id}`}
                    className="text-primary font-semibold hover:underline"
                  >
                    编辑
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-secondary border border-secondary rounded-2xl p-5">
          <p className="text-sm font-bold text-primary mb-2">发布建议</p>
          <p className="text-xs text-primary">发布前建议先点击 AI 预览，确认任务流程与评价维度完整。</p>
        </div>
        <div className="bg-success-soft border border-success/20 rounded-2xl p-5">
          <p className="text-sm font-bold text-success mb-2">知识库增强</p>
          <p className="text-xs text-success">可先在知识库上传教学资料，再用于作业设计时的 AI 生成。</p>
        </div>
        <div className="bg-warning-soft border border-warning/20 rounded-2xl p-5">
          <p className="text-sm font-bold text-warning mb-2">班级功能进展</p>
          <p className="text-xs text-warning flex items-center gap-1">
            <Archive className="w-3.5 h-3.5" /> 班级邀请码与基础分组能力已接入，可直接完成班级内分组。
          </p>
        </div>
      </section>
    </div>
  );
}

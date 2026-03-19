import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Clock,
  LayoutGrid,
  Sparkles,
  Users,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { PageState } from "../components/PageState";
import {
  assignmentsApi,
  classesApi,
  getApiErrorMessage,
  subjectsApi,
  type Assignment,
  type Classroom,
  type Subject,
} from "../lib/api";
import { stageToSchoolLevel } from "../lib/mappers";
import { StatusBanner } from "../components/StatusBanner";
import { validateInviteCode } from "../validation/classroom";

function gradeLabel(grade: number): string {
  if (grade <= 6) return `小学${grade}年级`;
  return `初中${Math.max(1, grade - 6)}年级`;
}

function inquiryDepthLabel(depth: string): string {
  if (depth === "basic") return "基础探究";
  if (depth === "intermediate") return "中等探究";
  if (depth === "deep") return "深度探究";
  return depth;
}

export function StudentDashboard() {
  const { user, refreshMe } = useAuth();
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [classes, setClasses] = useState<Classroom[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [joining, setJoining] = useState(false);
  const [joinCode, setJoinCode] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [reloadToken, setReloadToken] = useState(0);

  const retryLoad = () => {
    setReloadToken((value) => value + 1);
  };

  useEffect(() => {
    let mounted = true;

    async function loadData() {
      if (!user || user.role !== "student") {
        if (mounted) setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setError("");
      try {
        const [assignmentResp, subjectResp, classResp] = await Promise.all([
          assignmentsApi.list(1, 100, true),
          subjectsApi.list(),
          classesApi.listMy(),
        ]);
        if (!mounted) return;
        const allAssignments = assignmentResp.assignments || [];
        const visibleAssignments = user.grade
          ? allAssignments.filter((assignment) => assignment.grade === user.grade)
          : allAssignments;
        setAssignments(visibleAssignments);
        setSubjects(subjectResp.subjects || []);
        setClasses(classResp.classes || []);
      } catch (err) {
        if (!mounted) return;
        setError(getApiErrorMessage(err, "加载学生作业失败"));
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
    const map = new Map<number, string>();
    subjects.forEach((subject) => {
      map.set(subject.id, subject.name);
    });
    return map;
  }, [subjects]);

  const joinClassroom = async () => {
    const inviteCode = joinCode.trim();
    const inviteCodeError = validateInviteCode(inviteCode);
    if (inviteCodeError) {
      setError(inviteCodeError);
      return;
    }

    setJoining(true);
    setError("");
    setNotice("");
    try {
      const result = await classesApi.join(inviteCode);
      setNotice(`${result.message}：${result.classroom.name}`);
      setJoinCode("");
      await refreshMe();
      retryLoad();
    } catch (err) {
      setError(getApiErrorMessage(err, "入班失败，请检查邀请码后重试"));
    } finally {
      setJoining(false);
    }
  };

  if (!user || user.role !== "student") {
    return <PageState variant="warning" title="访问受限" description="当前账号不是学生身份，请切换学生账号登录。" actionLabel="返回教师首页" actionTo="/" />;
  }

  return (
    <div className="max-w-7xl mx-auto space-y-8">
      <section className="bg-gradient-to-r from-indigo-600 to-indigo-800 rounded-3xl p-8 text-white">
        <h1 className="text-3xl font-black mb-2">{user.name}，欢迎回来</h1>
        <p className="text-indigo-100">
          当前可查看 <span className="font-bold text-white">{assignments.length}</span> 个已发布跨学科作业。
        </p>
      </section>

      {notice && <StatusBanner tone="success" message={notice} />}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-3xl border border-slate-100 p-6">
            <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-indigo-600" /> 我的跨学科作业
            </h2>

            {isLoading && <p className="text-sm text-slate-500">加载中...</p>}
            {!isLoading && error && (
              <StatusBanner tone="error" message={error} actionLabel="重试加载" onAction={retryLoad} />
            )}

            <div className="space-y-4">
              {!isLoading && !error && assignments.length === 0 && (
                <p className="text-sm text-slate-500">当前没有可见作业，请联系老师发布后再查看。</p>
              )}

              {assignments.map((assignment) => (
                <div
                  key={assignment.id}
                  className="bg-slate-50 border border-slate-100 rounded-2xl p-5 hover:border-indigo-100 transition-all"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h3 className="text-lg font-bold text-slate-900">
                        <Link to={`/assignment/${assignment.id}`} className="hover:text-indigo-600 transition-colors">
                          {assignment.title}
                        </Link>
                      </h3>
                      <p className="text-xs text-slate-500 mt-1">
                        学段：{stageToSchoolLevel(assignment.school_stage)} · 年级：{gradeLabel(assignment.grade)} · 主学科：
                        {subjectById.get(assignment.main_subject_id) || "未匹配学科"}
                      </p>
                    </div>
                    <span className="px-2 py-1 rounded-full bg-emerald-50 text-emerald-700 text-[10px] font-bold">
                      已发布
                    </span>
                  </div>

                  <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                    <div className="p-2 bg-white rounded-lg border border-slate-100">
                      融合学科：
                      {assignment.related_subject_ids
                        .map((subjectId) => subjectById.get(subjectId) || `学科${subjectId}`)
                        .join("、") || "暂无"}
                    </div>
                    <div className="p-2 bg-white rounded-lg border border-slate-100">探究深度：{inquiryDepthLabel(assignment.inquiry_depth)}</div>
                  </div>

                  <div className="mt-4 flex items-center justify-between">
                    <div className="text-xs text-slate-500 flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5" /> 创建于 {assignment.created_at.slice(0, 10)}
                    </div>
                    <Link
                      to={`/assignment/${assignment.id}`}
                      className="text-xs font-bold text-indigo-600 hover:text-indigo-700 flex items-center gap-1"
                    >
                      进入任务 <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-6">
          <div className="bg-white rounded-3xl border border-slate-100 p-6">
            <h3 className="font-bold mb-4 flex items-center gap-2">
              <Users className="w-5 h-5 text-indigo-600" /> 班级邀请码能力
            </h3>
            <p className="text-sm text-slate-600 leading-relaxed">输入教师提供的邀请码即可入班。</p>
            <div className="mt-4 flex items-center gap-2">
              <input
                value={joinCode}
                onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
                placeholder="请输入邀请码"
                className="flex-1 px-3 py-2 rounded-lg border border-slate-200 text-sm"
              />
              <button
                onClick={joinClassroom}
                disabled={joining}
                className="px-3 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 disabled:opacity-60"
              >
                {joining ? "加入中..." : "加入班级"}
              </button>
            </div>
          </div>

          <div className="bg-white rounded-3xl border border-slate-100 p-6">
            <h3 className="font-bold mb-4 flex items-center gap-2">
              <LayoutGrid className="w-5 h-5 text-indigo-600" /> 我的班级与小组
            </h3>
            {classes.length === 0 ? (
              <p className="text-sm text-slate-500">你暂未加入任何班级。</p>
            ) : (
              <div className="space-y-2">
                {classes.map((item) => (
                  <div key={item.id} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                    <p className="text-sm font-semibold text-slate-800">{item.name}</p>
                    <p className="text-xs text-slate-500 mt-1">
                      {gradeLabel(item.grade)} · 教师：{item.teacher_name || "未显示"} · 成员 {item.member_count} 人 · 小组：
                      {item.joined_group_name || "未分组"}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="bg-amber-50 rounded-3xl border border-amber-100 p-6">
            <h4 className="font-bold text-amber-900 mb-3 flex items-center gap-2">
              <Sparkles className="w-4 h-4" /> 学习建议
            </h4>
            <p className="text-xs text-amber-700 leading-relaxed">
              建议优先完成“证据采集”与“数据解释”两类步骤，这会直接影响你的作业评价质量。
            </p>
            <div className="mt-4 flex items-center gap-1 text-emerald-600 text-xs font-semibold">
              <CheckCircle2 className="w-3.5 h-3.5" /> 按阶段提交，持续完善证据链
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

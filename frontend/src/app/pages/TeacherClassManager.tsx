import React, { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Copy, KeyRound, LoaderCircle, PlusCircle, RefreshCw, Trash2, Users } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { PageState } from "../components/PageState";
import { StatusBanner } from "../components/StatusBanner";
import {
  classesApi,
  getApiErrorMessage,
  type ClassGroup,
  type Classroom,
  type ClassroomMember,
} from "../lib/api";
import { validateClassroomName, validateGroupName } from "../validation/classroom";

function gradeLabel(grade: number): string {
  if (grade <= 6) return `小学${grade}年级`;
  return `初中${Math.max(1, grade - 6)}年级`;
}

export function TeacherClassManager() {
  const { user } = useAuth();

  const [classes, setClasses] = useState<Classroom[]>([]);
  const [selectedClassId, setSelectedClassId] = useState<number | null>(null);
  const [members, setMembers] = useState<ClassroomMember[]>([]);
  const [groups, setGroups] = useState<ClassGroup[]>([]);

  const [className, setClassName] = useState("");
  const [classGrade, setClassGrade] = useState(7);
  const [groupName, setGroupName] = useState("");

  const [loading, setLoading] = useState(true);
  const [membersLoading, setMembersLoading] = useState(false);
  const [groupsLoading, setGroupsLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [creatingGroup, setCreatingGroup] = useState(false);
  const [updatingStudentId, setUpdatingStudentId] = useState<number | null>(null);
  const [deletingGroupId, setDeletingGroupId] = useState<number | null>(null);
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const selectedClassroom = useMemo(
    () => classes.find((item) => item.id === selectedClassId) || null,
    [classes, selectedClassId],
  );

  const loadClasses = async () => {
    setError("");
    try {
      const result = await classesApi.listMy();
      const list = result.classes || [];
      setClasses(list);

      if (list.length === 0) {
        setSelectedClassId(null);
        setMembers([]);
        return;
      }

      setSelectedClassId((prev) => {
        if (prev && list.some((item) => item.id === prev)) return prev;
        return list[0].id;
      });
    } catch (err) {
      setError(getApiErrorMessage(err, "加载班级失败"));
    }
  };

  const loadMembers = async (classId: number) => {
    setMembersLoading(true);
    setError("");
    try {
      const result = await classesApi.listMembers(classId);
      setMembers(result.members || []);
      setClasses((prev) =>
        prev.map((item) =>
          item.id === classId
            ? {
                ...item,
                invite_code: result.classroom.invite_code,
                member_count: result.total,
              }
            : item,
        ),
      );
    } catch (err) {
      setError(getApiErrorMessage(err, "加载班级成员失败"));
      setMembers([]);
    } finally {
      setMembersLoading(false);
    }
  };

  const loadGroups = async (classId: number) => {
    setGroupsLoading(true);
    setError("");
    try {
      const result = await classesApi.listGroups(classId);
      setGroups(result.groups || []);
    } catch (err) {
      setError(getApiErrorMessage(err, "加载班级小组失败"));
      setGroups([]);
    } finally {
      setGroupsLoading(false);
    }
  };

  useEffect(() => {
    let mounted = true;

    async function bootstrap() {
      if (!user || user.role !== "teacher") {
        if (mounted) setLoading(false);
        return;
      }
      setLoading(true);
      await loadClasses();
      if (mounted) setLoading(false);
    }

    bootstrap();
    return () => {
      mounted = false;
    };
  }, [user]);

  useEffect(() => {
    if (!selectedClassId) {
      setMembers([]);
      setGroups([]);
      return;
    }
    loadMembers(selectedClassId);
    loadGroups(selectedClassId);
  }, [selectedClassId]);

  const createClassroom = async () => {
    const name = className.trim();
    const nameError = validateClassroomName(name);
    if (nameError) {
      setError(nameError);
      return;
    }

    setCreating(true);
    setError("");
    setNotice("");
    try {
      const created = await classesApi.create({
        name,
        grade: classGrade,
      });
      setClasses((prev) => [created, ...prev]);
      setSelectedClassId(created.id);
      setClassName("");
      setNotice(`班级创建成功：${created.name}`);
    } catch (err) {
      setError(getApiErrorMessage(err, "创建班级失败"));
    } finally {
      setCreating(false);
    }
  };

  const createGroup = async () => {
    if (!selectedClassroom) {
      setError("请先选择班级再创建小组");
      return;
    }
    const name = groupName.trim();
    const nameError = validateGroupName(
      name,
      groups.map((item) => item.name),
    );
    if (nameError) {
      setError(nameError);
      return;
    }

    setCreatingGroup(true);
    setError("");
    setNotice("");
    try {
      await classesApi.createGroup(selectedClassroom.id, name);
      setGroupName("");
      await Promise.all([loadGroups(selectedClassroom.id), loadMembers(selectedClassroom.id)]);
      setNotice(`小组创建成功：${name}`);
    } catch (err) {
      setError(getApiErrorMessage(err, "创建小组失败"));
    } finally {
      setCreatingGroup(false);
    }
  };

  const deleteGroup = async (group: ClassGroup) => {
    if (!selectedClassroom) return;
    const confirmed = window.confirm(`确认删除小组「${group.name}」吗？`);
    if (!confirmed) return;

    setDeletingGroupId(group.id);
    setError("");
    setNotice("");
    try {
      await classesApi.deleteGroup(selectedClassroom.id, group.id);
      await Promise.all([loadGroups(selectedClassroom.id), loadMembers(selectedClassroom.id)]);
      setNotice(`已删除小组：${group.name}`);
    } catch (err) {
      setError(getApiErrorMessage(err, "删除小组失败"));
    } finally {
      setDeletingGroupId(null);
    }
  };

  const changeStudentGroup = async (member: ClassroomMember, groupValue: string) => {
    if (!selectedClassroom) return;

    const nextGroupId = groupValue ? Number(groupValue) : null;
    if (groupValue && !Number.isFinite(nextGroupId)) {
      setError("小组参数无效");
      return;
    }
    if ((member.group_id ?? null) === nextGroupId) {
      return;
    }

    setUpdatingStudentId(member.student_id);
    setError("");
    setNotice("");
    try {
      if (nextGroupId === null) {
        if (member.group_id) {
          await classesApi.removeGroupMember(selectedClassroom.id, member.group_id, member.student_id);
        }
        setNotice(`已将 ${member.student_name} 移出小组`);
      } else {
        await classesApi.assignGroupMember(selectedClassroom.id, nextGroupId, member.student_id);
        const targetGroupName = groups.find((item) => item.id === nextGroupId)?.name || "目标小组";
        setNotice(`已将 ${member.student_name} 分配到「${targetGroupName}」`);
      }
      await Promise.all([loadMembers(selectedClassroom.id), loadGroups(selectedClassroom.id)]);
    } catch (err) {
      setError(getApiErrorMessage(err, "更新学生分组失败"));
    } finally {
      setUpdatingStudentId(null);
    }
  };

  const resetInviteCode = async () => {
    if (!selectedClassroom) return;
    setResetting(true);
    setError("");
    setNotice("");
    try {
      const updated = await classesApi.resetInviteCode(selectedClassroom.id);
      setClasses((prev) => prev.map((item) => (item.id === updated.id ? { ...item, invite_code: updated.invite_code } : item)));
      setNotice("邀请码已重置");
    } catch (err) {
      setError(getApiErrorMessage(err, "重置邀请码失败"));
    } finally {
      setResetting(false);
    }
  };

  const copyInviteCode = async () => {
    if (!selectedClassroom) return;
    try {
      await navigator.clipboard.writeText(selectedClassroom.invite_code);
      setNotice("邀请码已复制到剪贴板");
    } catch {
      setNotice(`邀请码：${selectedClassroom.invite_code}`);
    }
  };

  if (!user || user.role !== "teacher") {
    return <PageState variant="warning" title="访问受限" description="仅教师可访问班级管理页面。" actionLabel="返回学生首页" actionTo="/student" />;
  }

  if (loading) {
    return <PageState variant="loading" title="正在加载班级管理数据" description="正在同步班级与成员信息。" />;
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <section className="bg-white rounded-3xl border border-slate-100 p-6 space-y-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Users className="w-6 h-6 text-indigo-600" /> 班级与小组管理
          </h1>
          <p className="text-sm text-slate-500 mt-1">教师可创建班级、分发邀请码，并完成班级内小组创建与成员分配。</p>
        </div>

        {error && <StatusBanner tone="error" message={error} actionLabel="刷新" onAction={loadClasses} />}
        {notice && <StatusBanner tone="success" message={notice} />}

        <div className="grid grid-cols-1 md:grid-cols-[2fr,1fr,auto] gap-3">
          <input
            value={className}
            onChange={(e) => setClassName(e.target.value)}
            placeholder="输入班级名称，例如：初一(3)班"
            className="px-4 py-3 rounded-xl border border-slate-200"
          />
          <select
            value={classGrade}
            onChange={(e) => setClassGrade(Number(e.target.value))}
            className="px-4 py-3 rounded-xl border border-slate-200"
          >
            {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((grade) => (
              <option key={grade} value={grade}>
                {gradeLabel(grade)}
              </option>
            ))}
          </select>
          <button
            onClick={createClassroom}
            disabled={creating}
            className="px-4 py-3 rounded-xl bg-indigo-600 text-white font-semibold hover:bg-indigo-700 disabled:opacity-60 flex items-center justify-center gap-2"
          >
            {creating ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <PlusCircle className="w-4 h-4" />} 创建班级
          </button>
        </div>
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-[1.2fr,1.8fr] gap-6">
        <article className="bg-white rounded-3xl border border-slate-100 p-5 space-y-3">
          <h2 className="font-bold text-lg">我的班级</h2>
          {classes.length === 0 ? (
            <p className="text-sm text-slate-500">暂无班级，请先创建一个班级。</p>
          ) : (
            <div className="space-y-2">
              {classes.map((item) => (
                <button
                  key={item.id}
                  onClick={() => setSelectedClassId(item.id)}
                  className={`w-full text-left rounded-xl border p-3 transition-colors ${
                    selectedClassId === item.id
                      ? "border-indigo-300 bg-indigo-50"
                      : "border-slate-200 bg-white hover:bg-slate-50"
                  }`}
                >
                  <p className="text-sm font-semibold text-slate-800">{item.name}</p>
                  <p className="text-xs text-slate-500 mt-1">
                    {gradeLabel(item.grade)} · 成员 {item.member_count} 人
                  </p>
                </button>
              ))}
            </div>
          )}
        </article>

        <article className="bg-white rounded-3xl border border-slate-100 p-5 space-y-4">
          {!selectedClassroom ? (
            <p className="text-sm text-slate-500">请选择左侧班级查看详情。</p>
          ) : (
            <>
              <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                <div>
                  <h2 className="font-bold text-lg">{selectedClassroom.name}</h2>
                  <p className="text-xs text-slate-500">{gradeLabel(selectedClassroom.grade)} · 当前成员 {selectedClassroom.member_count} 人</p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={copyInviteCode}
                    className="px-3 py-2 rounded-lg border border-slate-200 text-sm font-semibold hover:bg-slate-50 flex items-center gap-1"
                  >
                    <Copy className="w-4 h-4" /> 复制邀请码
                  </button>
                  <button
                    onClick={resetInviteCode}
                    disabled={resetting}
                    className="px-3 py-2 rounded-lg border border-amber-200 text-amber-700 text-sm font-semibold hover:bg-amber-50 disabled:opacity-60 flex items-center gap-1"
                  >
                    {resetting ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />} 重置邀请码
                  </button>
                </div>
              </div>

              <div className="rounded-2xl border border-indigo-100 bg-indigo-50 p-4">
                <p className="text-xs text-indigo-700 mb-1 flex items-center gap-1">
                  <KeyRound className="w-3.5 h-3.5" /> 当前邀请码
                </p>
                <p className="text-2xl font-black tracking-[0.2em] text-indigo-700">{selectedClassroom.invite_code}</p>
              </div>

              <div className="space-y-3">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
                  <h3 className="text-sm font-bold text-slate-700">班级小组</h3>
                  <div className="flex items-center gap-2">
                    <input
                      value={groupName}
                      onChange={(e) => setGroupName(e.target.value)}
                      placeholder="输入小组名称，例如：第1组"
                      className="px-3 py-2 rounded-lg border border-slate-200 text-sm"
                    />
                    <button
                      onClick={createGroup}
                      disabled={creatingGroup}
                      className="px-3 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 disabled:opacity-60"
                    >
                      {creatingGroup ? "创建中..." : "创建小组"}
                    </button>
                  </div>
                </div>

                {groupsLoading ? (
                  <p className="text-sm text-slate-500 flex items-center gap-2">
                    <LoaderCircle className="w-4 h-4 animate-spin" /> 加载小组中...
                  </p>
                ) : groups.length === 0 ? (
                  <p className="text-sm text-slate-500">暂无小组，可先创建小组后再分配成员。</p>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {groups.map((group) => (
                      <div key={group.id} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-sm font-semibold text-slate-800">{group.name}</p>
                          <button
                            onClick={() => deleteGroup(group)}
                            disabled={deletingGroupId === group.id}
                            className="text-xs px-2 py-1 rounded-md border border-red-200 text-red-600 hover:bg-red-50 disabled:opacity-60 flex items-center gap-1"
                          >
                            {deletingGroupId === group.id ? <LoaderCircle className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />} 删除
                          </button>
                        </div>
                        <p className="text-xs text-slate-500 mt-1">成员 {group.member_count} 人</p>
                        <p className="text-xs text-slate-500 mt-1">
                          {(group.members || []).map((member) => member.student_name).join("、") || "暂无成员"}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div>
                <h3 className="text-sm font-bold text-slate-700 mb-2">入班学生与分组</h3>
                {membersLoading ? (
                  <p className="text-sm text-slate-500 flex items-center gap-2">
                    <LoaderCircle className="w-4 h-4 animate-spin" /> 加载成员中...
                  </p>
                ) : members.length === 0 ? (
                  <p className="text-sm text-slate-500">暂无学生入班，可将邀请码发给学生加入。</p>
                ) : (
                  <div className="space-y-2">
                    {members.map((member) => (
                      <div key={member.member_id} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-2">
                          <div>
                            <p className="text-sm font-semibold text-slate-800">{member.student_name}</p>
                            <p className="text-xs text-slate-500 mt-1">
                              学号：{member.student_username} · 年级：{member.student_grade ? gradeLabel(member.student_grade) : "未设置"}
                            </p>
                          </div>
                          <div className="min-w-[180px]">
                            <select
                              value={member.group_id ? String(member.group_id) : ""}
                              onChange={(e) => changeStudentGroup(member, e.target.value)}
                              disabled={updatingStudentId === member.student_id}
                              className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm"
                            >
                              <option value="">未分组</option>
                              {groups.map((group) => (
                                <option key={group.id} value={group.id}>
                                  {group.name}
                                </option>
                              ))}
                            </select>
                          </div>
                        </div>
                        <p className="text-[11px] text-slate-500 mt-1">当前小组：{member.group_name || "未分组"}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </article>
      </section>

      <section className="bg-emerald-50 border border-emerald-100 rounded-2xl p-4 text-xs text-emerald-800 flex items-center gap-2">
        <CheckCircle2 className="w-4 h-4" />
        班级与小组能力已接入：支持邀请码入班、小组创建、成员分配与分组调整。
      </section>
    </div>
  );
}

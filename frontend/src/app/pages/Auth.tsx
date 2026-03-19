import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";
import {
  Lock,
  User,
  ArrowRight,
  GraduationCap,
  School,
  Sparkles,
  IdCard,
  Smartphone,
} from "lucide-react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type { Role } from "../data/models";
import { useAuth } from "../context/AuthContext";
import { getApiErrorMessage } from "../lib/api";
import { validateLoginInput, validateRegisterInput } from "../validation/auth";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function Auth() {
  const navigate = useNavigate();
  const { login, register, logout, isAuthenticated, user } = useAuth();

  const [mode, setMode] = useState<"login" | "register">("login");
  const [role, setRole] = useState<Role>("teacher");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [loginIdentifier, setLoginIdentifier] = useState("");
  const [loginPassword, setLoginPassword] = useState("");

  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [identityCode, setIdentityCode] = useState("");
  const [studentGrade, setStudentGrade] = useState(7);
  const [studentClassName, setStudentClassName] = useState("1班");
  const [registerPassword, setRegisterPassword] = useState("");

  const identityLabel = role === "teacher" ? "工号" : "学号";
  const loginLabel = role === "teacher" ? "工号" : "学号";

  const loginPlaceholder = role === "teacher" ? "请输入工号" : "请输入学号";

  useEffect(() => {
    if (!isAuthenticated || !user) return;
    navigate(user.role === "teacher" ? "/" : "/student", { replace: true });
  }, [isAuthenticated, user, navigate]);

  const resetError = () => setError("");

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    resetError();

    const identifier = loginIdentifier.trim();
    const loginError = validateLoginInput(identifier, loginPassword, loginLabel);
    if (loginError) {
      setError(loginError);
      return;
    }

    setLoading(true);
    try {
      const currentUser = await login(identifier, loginPassword, role);
      if (currentUser.role !== role) {
        logout();
        setError(`该账号为${currentUser.role === "teacher" ? "教师" : "学生"}身份，请切换身份选项后登录`);
        return;
      }
      navigate(currentUser.role === "teacher" ? "/" : "/student", { replace: true });
    } catch (err) {
      setError(getApiErrorMessage(err, `${loginLabel}或密码错误`));
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    resetError();

    const trimmedName = name.trim();
    const trimmedIdentity = identityCode.trim();
    const trimmedPhone = phone.trim();
    const trimmedClassName = studentClassName.trim();

    const registerError = validateRegisterInput({
      role,
      name: trimmedName,
      identifier: trimmedIdentity,
      password: registerPassword,
      grade: studentGrade,
      className: trimmedClassName,
      phone: trimmedPhone,
    });
    if (registerError) {
      setError(registerError);
      return;
    }

    setLoading(true);
    try {
      const currentUser = await register({
        username: trimmedIdentity,
        role,
        name: trimmedName,
        password: registerPassword,
        grade: role === "student" ? studentGrade : undefined,
        class_name: role === "student" ? trimmedClassName || undefined : undefined,
      });
      navigate(currentUser.role === "teacher" ? "/" : "/student", { replace: true });
    } catch (err) {
      setError(getApiErrorMessage(err, "注册失败，请检查输入后重试"));
    } finally {
      setLoading(false);
    }
  };

  const roleDesc = useMemo(() => {
    return role === "teacher"
      ? "教师使用工号登录，进行跨学科作业设计与发布。"
      : "学生使用学号登录，查看并完成已发布作业。";
  }, [role]);

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6 relative overflow-hidden">
      <div className="absolute top-0 right-0 -translate-y-1/2 translate-x-1/2 w-[600px] h-[600px] bg-indigo-100 rounded-full blur-3xl opacity-50" />
      <div className="absolute bottom-0 left-0 translate-y-1/2 -translate-x-1/2 w-[400px] h-[400px] bg-emerald-50 rounded-full blur-3xl opacity-50" />

      <div className="w-full max-w-5xl bg-white rounded-[40px] shadow-2xl shadow-indigo-100 flex overflow-hidden relative z-10 border border-slate-100">
        <div className="hidden lg:flex flex-1 bg-indigo-600 p-12 text-white flex-col justify-between relative overflow-hidden">
          <div className="relative z-10">
            <div className="w-12 h-12 bg-white rounded-2xl flex items-center justify-center text-indigo-600 font-black text-2xl mb-6 shadow-xl">
              C
            </div>
            <h1 className="text-4xl font-black mb-4 leading-tight">构建跨学科探究的桥梁</h1>
            <p className="text-indigo-100 text-lg">CDAS 跨学科作业系统，助力 K12 教育数字化转型。</p>
          </div>

          <div className="relative z-10 space-y-6">
            <div className="flex items-center gap-4 bg-white/10 backdrop-blur-md p-4 rounded-2xl border border-white/10">
              <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-amber-300" />
              </div>
              <p className="text-sm font-medium">账号规则：教师工号登录，学生学号登录</p>
            </div>
            <div className="flex items-center gap-4 bg-white/10 backdrop-blur-md p-4 rounded-2xl border border-white/10">
              <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center">
                <IdCard className="w-5 h-5 text-emerald-300" />
              </div>
              <p className="text-sm font-medium">已接入真实后端接口，支持多端数据同步</p>
            </div>
          </div>

          <div className="absolute -bottom-20 -right-20 w-80 h-80 bg-indigo-500 rounded-full blur-3xl opacity-50" />
        </div>

        <div className="w-full lg:w-[480px] p-10 md:p-16 flex flex-col">
          <div className="mb-8">
            <h2 className="text-2xl font-black text-slate-900 mb-2">{mode === "login" ? "账号登录" : "账号注册"}</h2>
            <p className="text-slate-500 text-sm">{roleDesc}</p>
          </div>

          <div className="flex p-1 bg-slate-100 rounded-2xl mb-8 relative">
            <div
              className={cn(
                "absolute top-1 bottom-1 w-[calc(50%-4px)] bg-white rounded-xl shadow-sm transition-all duration-300 ease-out",
                role === "teacher" ? "left-1" : "left-[calc(50%+2px)]",
              )}
            />
            <button
              onClick={() => {
                setRole("teacher");
                resetError();
              }}
              className={cn(
                "flex-1 py-3 text-xs font-bold rounded-xl relative z-10 transition-colors flex items-center justify-center gap-2",
                role === "teacher" ? "text-indigo-600" : "text-slate-400",
              )}
            >
              <School className="w-3.5 h-3.5" /> 我是教师
            </button>
            <button
              onClick={() => {
                setRole("student");
                resetError();
              }}
              className={cn(
                "flex-1 py-3 text-xs font-bold rounded-xl relative z-10 transition-colors flex items-center justify-center gap-2",
                role === "student" ? "text-indigo-600" : "text-slate-400",
              )}
            >
              <GraduationCap className="w-3.5 h-3.5" /> 我是学生
            </button>
          </div>

          {mode === "login" ? (
            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <label className="text-xs font-black uppercase text-slate-400 tracking-widest">{loginLabel}</label>
                <div className="relative mt-2">
                  <User className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <input
                    value={loginIdentifier}
                    onChange={(e) => setLoginIdentifier(e.target.value)}
                    placeholder={loginPlaceholder}
                    className="w-full pl-11 pr-4 py-3.5 bg-slate-50 border border-slate-100 rounded-2xl outline-none focus:ring-2 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all text-sm font-medium"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-black uppercase text-slate-400 tracking-widest">登录密码</label>
                <div className="relative mt-2">
                  <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <input
                    type="password"
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                    placeholder="至少 8 位密码"
                    className="w-full pl-11 pr-4 py-3.5 bg-slate-50 border border-slate-100 rounded-2xl outline-none focus:ring-2 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all text-sm font-medium"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-4 bg-indigo-600 text-white rounded-2xl font-bold shadow-lg shadow-indigo-100 hover:bg-indigo-700 transition-all flex items-center justify-center gap-2"
              >
                {loading ? "登录中..." : "确认登录"}
                {!loading && <ArrowRight className="w-4 h-4" />}
              </button>
            </form>
          ) : (
            <form onSubmit={handleRegister} className="space-y-4">
              <div>
                <label className="text-xs font-black uppercase text-slate-400 tracking-widest">姓名</label>
                <div className="relative mt-2">
                  <User className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="请输入真实姓名"
                    className="w-full pl-11 pr-4 py-3.5 bg-slate-50 border border-slate-100 rounded-2xl outline-none focus:ring-2 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all text-sm font-medium"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-black uppercase text-slate-400 tracking-widest">{identityLabel}</label>
                <div className="relative mt-2">
                  <IdCard className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <input
                    value={identityCode}
                    onChange={(e) => setIdentityCode(e.target.value)}
                    placeholder={`请输入${identityLabel}`}
                    className="w-full pl-11 pr-4 py-3.5 bg-slate-50 border border-slate-100 rounded-2xl outline-none focus:ring-2 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all text-sm font-medium"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-black uppercase text-slate-400 tracking-widest">手机号</label>
                <div className="relative mt-2">
                  <Smartphone className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <input
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="可选，仅用于后续扩展"
                    className="w-full pl-11 pr-4 py-3.5 bg-slate-50 border border-slate-100 rounded-2xl outline-none focus:ring-2 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all text-sm font-medium"
                  />
                </div>
                <p className="mt-2 text-[11px] text-slate-400">当前后端暂不保存手机号，仅保留注册必填字段。</p>
              </div>

              {role === "student" && (
                <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="text-xs font-black uppercase text-slate-400 tracking-widest">年级</label>
                      <select
                        value={studentGrade}
                        onChange={(e) => setStudentGrade(Number(e.target.value))}
                        className="w-full mt-2 px-4 py-3.5 bg-slate-50 border border-slate-100 rounded-2xl outline-none focus:ring-2 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all text-sm font-medium"
                      >
                        <option value={1}>小学一年级</option>
                        <option value={2}>小学二年级</option>
                        <option value={3}>小学三年级</option>
                        <option value={4}>小学四年级</option>
                        <option value={5}>小学五年级</option>
                        <option value={6}>小学六年级</option>
                        <option value={7}>初中一年级</option>
                        <option value={8}>初中二年级</option>
                        <option value={9}>初中三年级</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-xs font-black uppercase text-slate-400 tracking-widest">班级</label>
                      <input
                        value={studentClassName}
                        onChange={(e) => setStudentClassName(e.target.value)}
                        placeholder="例如：1班"
                        className="w-full mt-2 px-4 py-3.5 bg-slate-50 border border-slate-100 rounded-2xl outline-none focus:ring-2 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all text-sm font-medium"
                      />
                    </div>
                  </div>
                )}

              <div>
                <label className="text-xs font-black uppercase text-slate-400 tracking-widest">设置密码</label>
                <div className="relative mt-2">
                  <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <input
                    type="password"
                    value={registerPassword}
                    onChange={(e) => setRegisterPassword(e.target.value)}
                    placeholder="至少 8 位密码"
                    className="w-full pl-11 pr-4 py-3.5 bg-slate-50 border border-slate-100 rounded-2xl outline-none focus:ring-2 focus:ring-indigo-500/10 focus:border-indigo-500 transition-all text-sm font-medium"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-4 bg-indigo-600 text-white rounded-2xl font-bold shadow-lg shadow-indigo-100 hover:bg-indigo-700 transition-all flex items-center justify-center gap-2"
              >
                {loading ? "注册中..." : "完成注册"}
                {!loading && <ArrowRight className="w-4 h-4" />}
              </button>
            </form>
          )}

          {error && <p className="mt-4 text-sm font-medium text-red-500">{error}</p>}

          <div className="mt-8 pt-8 border-t border-slate-50 text-center">
            <p className="text-sm text-slate-500">
              {mode === "login" ? "还没有账户？" : "已有账户？"}
              <button
                onClick={() => {
                  setMode(mode === "login" ? "register" : "login");
                  resetError();
                }}
                className="text-indigo-600 font-bold ml-1 hover:underline"
              >
                {mode === "login" ? "立即注册" : "点击登录"}
              </button>
            </p>
          </div>

          <div className="mt-auto pt-6 text-[10px] text-slate-400 text-center leading-relaxed">
            登录即代表您同意我们的 <button className="underline">服务协议</button> 和 <button className="underline">隐私政策</button>
            <br />
            CDAS © 2026 跨学科教育数字化平台
          </div>
        </div>
      </div>
    </div>
  );
}

import React, { useEffect } from "react";
import { Outlet, NavLink, useLocation, useNavigate } from "react-router";
import {
  LayoutDashboard,
  PlusCircle,
  BookMarked,
  Library,
  Bell,
  Search,
  ChevronRight,
  UserCircle,
  LogOut,
  Users,
} from "lucide-react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { useAuth } from "../context/AuthContext";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function Root() {
  const { user, isLoading, isAuthenticated, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      navigate("/auth", { replace: true });
    }
  }, [isLoading, isAuthenticated, navigate]);

  useEffect(() => {
    if (isLoading || !user) return;
    const pathname = location.pathname;

    if (user.role === "student") {
      const teacherOnlyPrefixes = ["/create", "/classes", "/grading", "/knowledge"];
      if (pathname === "/" || teacherOnlyPrefixes.some((prefix) => pathname.startsWith(prefix))) {
        navigate("/student", { replace: true });
      }
      return;
    }

    if (user.role === "teacher" && pathname.startsWith("/student")) {
      navigate("/", { replace: true });
    }
  }, [isLoading, user, location.pathname, navigate]);

  if (isLoading || !user) {
    return <div className="min-h-screen bg-slate-50" />;
  }

  const role = user.role;

  const teacherNavItems = [
    { icon: LayoutDashboard, label: "仪表盘", path: "/" },
    { icon: PlusCircle, label: "设计作业", path: "/create" },
    { icon: Users, label: "班级与小组", path: "/classes" },
    { icon: Library, label: "知识库", path: "/knowledge" },
  ];

  const studentNavItems = [
    { icon: LayoutDashboard, label: "我的探索", path: "/student" },
    { icon: BookMarked, label: "作业指引", path: "/student" },
  ];

  const navItems = role === "teacher" ? teacherNavItems : studentNavItems;

  const handleLogout = () => {
    logout();
    navigate("/auth", { replace: true });
  };

  const subtitle =
    role === "teacher"
      ? `教师账号：${user.username}`
      : `学生账号：${user.username}`;

  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900 font-sans">
      <aside className="w-64 border-r border-slate-200 bg-white flex flex-col sticky top-0 h-screen">
        <div className="p-6 flex items-center gap-3">
          <div className="w-10 h-10 bg-indigo-600 rounded-xl flex items-center justify-center text-white font-bold text-xl">
            C
          </div>
          <div>
            <h1 className="font-bold text-lg leading-tight">CDAS</h1>
            <p className="text-xs text-slate-500">跨学科作业系统</p>
          </div>
        </div>

        <nav className="flex-1 px-4 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={`${item.path}-${item.label}`}
              to={item.path}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                  isActive ? "bg-indigo-50 text-indigo-700" : "text-slate-600 hover:bg-slate-100",
                )
              }
            >
              <item.icon className="w-5 h-5" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-slate-100 space-y-3">
          <div className="bg-slate-50 rounded-xl p-4">
            <div className="flex items-center gap-3 mb-3">
              <div
                className={cn(
                  "w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold",
                  role === "teacher" ? "bg-indigo-100 text-indigo-700" : "bg-emerald-100 text-emerald-700",
                )}
              >
                {role === "teacher" ? "T" : "S"}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold truncate">{user.name || "未登录"}</p>
                <p className="text-[10px] text-slate-500 truncate">{subtitle}</p>
              </div>
            </div>
            <button className="w-full flex items-center justify-between text-xs text-slate-600 hover:text-indigo-600 font-medium">
              个人设置
              <ChevronRight className="w-3 h-3" />
            </button>
          </div>
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-3 py-2 text-red-500 hover:bg-red-50 rounded-lg text-sm font-bold transition-colors"
          >
            <LogOut className="w-4 h-4" />
            退出登录
          </button>
        </div>
      </aside>

      <main className="flex-1 flex flex-col">
        <header className="h-16 border-b border-slate-200 bg-white px-8 flex items-center justify-between sticky top-0 z-10">
          <div className="flex items-center gap-4 bg-slate-50 px-4 py-2 rounded-lg w-96">
            <Search className="w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="搜索作业、课标、文档..."
              className="bg-transparent border-none outline-none text-sm w-full"
            />
          </div>
          <div className="flex items-center gap-4">
            <button className="relative p-2 text-slate-500 hover:bg-slate-50 rounded-lg transition-colors">
              <Bell className="w-5 h-5" />
              <span className="absolute top-1 right-1 w-2 h-2 bg-red-500 rounded-full border-2 border-white" />
            </button>
            <div className="h-8 w-px bg-slate-200 mx-2" />
            {role === "teacher" ? (
              <button
                onClick={() => navigate("/create")}
                className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors flex items-center gap-2"
              >
                <PlusCircle className="w-4 h-4" />
                发布作业
              </button>
            ) : (
              <div className="flex items-center gap-2 text-sm font-bold text-slate-600">
                <UserCircle className="w-5 h-5" />
                欢迎, {user.name || "同学"}
              </div>
            )}
          </div>
        </header>

        <div className="flex-1 p-8 overflow-auto">
          <Outlet />
        </div>
      </main>
    </div>
  );
}

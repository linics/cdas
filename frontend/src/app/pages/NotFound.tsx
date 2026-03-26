import React from "react";
import { Link } from "react-router";
import { Compass, Home, LogIn } from "lucide-react";
import { useAuth } from "../context/AuthContext";

export function NotFound() {
  const { user, isAuthenticated } = useAuth();

  const homePath = user?.role === "student" ? "/student" : "/";

  return (
    <div className="max-w-3xl mx-auto bg-surface border border-border rounded-2xl p-10 text-center space-y-4">
      <div className="mx-auto w-14 h-14 rounded-2xl bg-secondary text-primary flex items-center justify-center">
        <Compass className="w-7 h-7" />
      </div>
      <h1 className="text-3xl font-black text-text">页面不存在</h1>
      <p className="text-sm text-text-secondary">你访问的地址无效，可能已被移动或删除。</p>
      <div className="flex items-center justify-center gap-3 pt-2">
        {isAuthenticated ? (
          <Link
            to={homePath}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-primary text-white text-sm font-semibold hover:bg-primary-hover active:bg-primary-active"
          >
            <Home className="w-4 h-4" /> 返回首页
          </Link>
        ) : (
          <Link
            to="/auth"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-primary text-white text-sm font-semibold hover:bg-primary-hover active:bg-primary-active"
          >
            <LogIn className="w-4 h-4" /> 返回登录
          </Link>
        )}
      </div>
    </div>
  );
}

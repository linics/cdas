import React from "react";
import { Link } from "react-router";
import { AlertCircle, Info, LoaderCircle, ShieldAlert } from "lucide-react";

type PageStateVariant = "loading" | "info" | "warning" | "error";

interface PageStateProps {
  title: string;
  description?: string;
  variant?: PageStateVariant;
  actionLabel?: string;
  onAction?: () => void;
  actionTo?: string;
}

function variantStyle(variant: PageStateVariant) {
  if (variant === "error") {
    return {
      wrapper: "border-red-100 bg-red-50",
      iconWrapper: "bg-red-100 text-red-600",
      icon: AlertCircle,
      title: "text-red-700",
      desc: "text-red-600",
    };
  }

  if (variant === "warning") {
    return {
      wrapper: "border-amber-100 bg-amber-50",
      iconWrapper: "bg-amber-100 text-amber-700",
      icon: ShieldAlert,
      title: "text-amber-800",
      desc: "text-amber-700",
    };
  }

  if (variant === "loading") {
    return {
      wrapper: "border-slate-100 bg-white",
      iconWrapper: "bg-slate-100 text-slate-600",
      icon: LoaderCircle,
      title: "text-slate-800",
      desc: "text-slate-500",
    };
  }

  return {
    wrapper: "border-slate-100 bg-white",
    iconWrapper: "bg-indigo-100 text-indigo-600",
    icon: Info,
    title: "text-slate-800",
    desc: "text-slate-500",
  };
}

export function PageState({
  title,
  description,
  variant = "info",
  actionLabel,
  onAction,
  actionTo,
}: PageStateProps) {
  const style = variantStyle(variant);
  const Icon = style.icon;

  return (
    <div className={`max-w-4xl mx-auto border rounded-3xl p-8 text-center ${style.wrapper}`}>
      <div className={`mx-auto w-11 h-11 rounded-xl flex items-center justify-center mb-3 ${style.iconWrapper}`}>
        <Icon className={`w-5 h-5 ${variant === "loading" ? "animate-spin" : ""}`} />
      </div>
      <h2 className={`text-lg font-bold ${style.title}`}>{title}</h2>
      {description && <p className={`text-sm mt-1 ${style.desc}`}>{description}</p>}

      {actionLabel && onAction && (
        <button
          onClick={onAction}
          className="mt-5 px-4 py-2 rounded-xl bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700"
        >
          {actionLabel}
        </button>
      )}

      {actionLabel && actionTo && (
        <Link
          to={actionTo}
          className="inline-flex mt-5 px-4 py-2 rounded-xl bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700"
        >
          {actionLabel}
        </Link>
      )}
    </div>
  );
}

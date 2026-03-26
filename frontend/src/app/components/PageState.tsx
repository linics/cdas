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
      wrapper: "border-danger/20 bg-danger-soft",
      iconWrapper: "bg-surface text-danger",
      icon: AlertCircle,
      title: "text-danger",
      desc: "text-danger",
    };
  }

  if (variant === "warning") {
    return {
      wrapper: "border-warning/20 bg-warning-soft",
      iconWrapper: "bg-surface text-warning",
      icon: ShieldAlert,
      title: "text-warning",
      desc: "text-warning",
    };
  }

  if (variant === "loading") {
    return {
      wrapper: "border-border bg-surface",
      iconWrapper: "bg-surface-muted text-text-secondary",
      icon: LoaderCircle,
      title: "text-text",
      desc: "text-text-secondary",
    };
  }

  return {
    wrapper: "border-border bg-surface",
    iconWrapper: "bg-info-soft text-info",
    icon: Info,
    title: "text-text",
    desc: "text-text-secondary",
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
    <div className={`max-w-4xl mx-auto border rounded-2xl p-8 text-center ${style.wrapper}`}>
      <div className={`mx-auto w-11 h-11 rounded-xl flex items-center justify-center mb-3 ${style.iconWrapper}`}>
        <Icon className={`w-5 h-5 ${variant === "loading" ? "animate-spin" : ""}`} />
      </div>
      <h2 className={`text-lg font-bold ${style.title}`}>{title}</h2>
      {description && <p className={`text-sm mt-1 ${style.desc}`}>{description}</p>}

      {actionLabel && onAction && (
        <button
          onClick={onAction}
          className="mt-5 px-4 py-2 rounded-xl bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary-hover active:bg-primary-active"
        >
          {actionLabel}
        </button>
      )}

      {actionLabel && actionTo && (
        <Link
          to={actionTo}
          className="inline-flex mt-5 px-4 py-2 rounded-xl bg-primary text-primary-foreground text-sm font-semibold hover:bg-primary-hover active:bg-primary-active"
        >
          {actionLabel}
        </Link>
      )}
    </div>
  );
}

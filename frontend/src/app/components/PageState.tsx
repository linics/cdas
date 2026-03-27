import React from "react";
import { Link } from "react-router";
import { AlertCircle, Info, LoaderCircle, ShieldAlert } from "lucide-react";

import { Button } from "./ui/button";

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
      iconWrapper: "bg-surface text-danger-on-soft",
      icon: AlertCircle,
      title: "text-danger-on-soft",
      desc: "text-danger-on-soft",
      actionVariant: "destructive" as const,
    };
  }

  if (variant === "warning") {
    return {
      wrapper: "border-warning/20 bg-warning-soft",
      iconWrapper: "bg-surface text-warning-on-soft",
      icon: ShieldAlert,
      title: "text-warning-on-soft",
      desc: "text-warning-on-soft",
      actionVariant: "warning" as const,
    };
  }

  if (variant === "loading") {
    return {
      wrapper: "border-border bg-surface",
      iconWrapper: "bg-surface-muted text-text-secondary",
      icon: LoaderCircle,
      title: "text-text",
      desc: "text-text-secondary",
      actionVariant: "secondary" as const,
    };
  }

  return {
    wrapper: "border-border bg-surface",
    iconWrapper: "bg-info-soft text-info-on-soft",
    icon: Info,
    title: "text-text",
    desc: "text-text-secondary",
    actionVariant: "info" as const,
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
    <div className={`mx-auto max-w-4xl rounded-2xl border p-8 text-center shadow-soft ${style.wrapper}`}>
      <div className={`mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-xl ${style.iconWrapper}`}>
        <Icon className={`h-5 w-5 ${variant === "loading" ? "animate-spin" : ""}`} />
      </div>
      <h2 className={`text-lg font-bold ${style.title}`}>{title}</h2>
      {description && <p className={`text-sm mt-1 ${style.desc}`}>{description}</p>}

      {actionLabel && onAction && (
        <Button
          onClick={onAction}
          variant={style.actionVariant}
          className="mt-5 rounded-xl px-4"
        >
          {actionLabel}
        </Button>
      )}

      {actionLabel && actionTo && (
        <Button asChild variant={style.actionVariant} className="mt-5 rounded-xl px-4">
          <Link to={actionTo}>{actionLabel}</Link>
        </Button>
      )}
    </div>
  );
}

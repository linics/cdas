import React from "react";
import { AlertCircle, CheckCircle2, Info, ShieldAlert } from "lucide-react";

type StatusTone = "success" | "error" | "info" | "warning";

interface StatusBannerProps {
  tone?: StatusTone;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
}

function toneStyle(tone: StatusTone) {
  if (tone === "success") {
    return {
      wrapper: "bg-success-soft border-success/20 text-success",
      button: "border-success/25 text-success hover:bg-success-soft/80",
      Icon: CheckCircle2,
    };
  }

  if (tone === "error") {
    return {
      wrapper: "bg-danger-soft border-danger/20 text-danger",
      button: "border-danger/25 text-danger hover:bg-danger-soft/80",
      Icon: AlertCircle,
    };
  }

  if (tone === "warning") {
    return {
      wrapper: "bg-warning-soft border-warning/20 text-warning",
      button: "border-warning/25 text-warning hover:bg-warning-soft/80",
      Icon: ShieldAlert,
    };
  }

  return {
    wrapper: "bg-info-soft border-info/20 text-info",
    button: "border-info/25 text-info hover:bg-info-soft/80",
    Icon: Info,
  };
}

export function StatusBanner({
  tone = "info",
  message,
  actionLabel,
  onAction,
  className = "",
}: StatusBannerProps) {
  const { wrapper, button, Icon } = toneStyle(tone);

  return (
    <div className={`rounded-2xl border px-4 py-3 text-sm flex items-center gap-2 ${wrapper} ${className}`.trim()}>
      <Icon className="w-4 h-4 shrink-0" />
      <span className="leading-relaxed">{message}</span>
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          className={`ml-auto px-2.5 py-1 rounded-lg border bg-surface text-xs font-semibold ${button}`}
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}

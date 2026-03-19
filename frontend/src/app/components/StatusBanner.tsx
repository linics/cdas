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
      wrapper: "bg-emerald-50 border-emerald-100 text-emerald-700",
      button: "border-emerald-200 text-emerald-700 hover:bg-emerald-100",
      Icon: CheckCircle2,
    };
  }

  if (tone === "error") {
    return {
      wrapper: "bg-red-50 border-red-100 text-red-600",
      button: "border-red-200 text-red-600 hover:bg-red-100",
      Icon: AlertCircle,
    };
  }

  if (tone === "warning") {
    return {
      wrapper: "bg-amber-50 border-amber-100 text-amber-700",
      button: "border-amber-200 text-amber-700 hover:bg-amber-100",
      Icon: ShieldAlert,
    };
  }

  return {
    wrapper: "bg-indigo-50 border-indigo-100 text-indigo-700",
    button: "border-indigo-200 text-indigo-700 hover:bg-indigo-100",
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
          className={`ml-auto px-2.5 py-1 rounded-lg border bg-white text-xs font-semibold ${button}`}
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}

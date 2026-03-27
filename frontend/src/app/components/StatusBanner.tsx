import React from "react";
import { AlertCircle, CheckCircle2, Info, ShieldAlert } from "lucide-react";

import { Button } from "./ui/button";

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
      wrapper: "bg-success-soft border-success/20 text-success-on-soft",
      Icon: CheckCircle2,
      buttonVariant: "success" as const,
    };
  }

  if (tone === "error") {
    return {
      wrapper: "bg-danger-soft border-danger/20 text-danger-on-soft",
      Icon: AlertCircle,
      buttonVariant: "destructive" as const,
    };
  }

  if (tone === "warning") {
    return {
      wrapper: "bg-warning-soft border-warning/20 text-warning-on-soft",
      Icon: ShieldAlert,
      buttonVariant: "warning" as const,
    };
  }

  return {
    wrapper: "bg-info-soft border-info/20 text-info-on-soft",
    Icon: Info,
    buttonVariant: "info" as const,
  };
}

export function StatusBanner({
  tone = "info",
  message,
  actionLabel,
  onAction,
  className = "",
}: StatusBannerProps) {
  const { wrapper, Icon, buttonVariant } = toneStyle(tone);

  return (
    <div className={`flex items-center gap-2 rounded-2xl border px-4 py-3 text-sm shadow-soft ${wrapper} ${className}`.trim()}>
      <Icon className="h-4 w-4 shrink-0" />
      <span className="leading-relaxed">{message}</span>
      {actionLabel && onAction && (
        <Button
          onClick={onAction}
          variant={buttonVariant}
          size="sm"
          className="ml-auto shrink-0 rounded-lg px-3 text-xs"
        >
          {actionLabel}
        </Button>
      )}
    </div>
  );
}

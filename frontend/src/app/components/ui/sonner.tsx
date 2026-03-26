"use client";

import { useTheme } from "next-themes";
import { Toaster as Sonner, ToasterProps } from "sonner";

const Toaster = ({ ...props }: ToasterProps) => {
  const { theme = "system" } = useTheme();

  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      className="toaster group"
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
          "--success-bg": "var(--success-soft)",
          "--success-text": "var(--success-base)",
          "--success-border": "color-mix(in srgb, var(--success-base) 20%, var(--surface))",
          "--error-bg": "var(--danger-soft)",
          "--error-text": "var(--danger-base)",
          "--error-border": "color-mix(in srgb, var(--danger-base) 20%, var(--surface))",
          "--warning-bg": "var(--warning-soft)",
          "--warning-text": "var(--warning-base)",
          "--warning-border": "color-mix(in srgb, var(--warning-base) 20%, var(--surface))",
        } as React.CSSProperties
      }
      {...props}
    />
  );
};

export { Toaster };

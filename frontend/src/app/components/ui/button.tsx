import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "./utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-[color,background-color,border-color,box-shadow,transform] disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:border-focus-ring focus-visible:ring-focus-ring/40 focus-visible:ring-[3px] aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary-hover active:bg-primary-active",
        destructive:
          "bg-danger text-destructive-foreground hover:bg-danger/90 active:bg-danger/95 focus-visible:ring-destructive/20 dark:focus-visible:ring-destructive/40",
        outline:
          "border border-border bg-surface text-text hover:bg-accent hover:text-accent-foreground",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-accent active:bg-accent/90",
        success:
          "bg-success text-primary-foreground hover:bg-success/90 active:bg-success/95",
        warning:
          "bg-warning text-primary-foreground hover:bg-warning/90 active:bg-warning/95",
        info:
          "bg-info text-primary-foreground hover:bg-info/90 active:bg-info/95",
        neutral:
          "bg-surface-muted text-text hover:bg-accent active:bg-accent/90",
        ghost: "hover:bg-accent hover:text-accent-foreground active:bg-accent/90",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 min-h-9 px-4 py-2 has-[>svg]:px-3",
        sm: "h-8 min-h-8 rounded-md gap-1.5 px-3 has-[>svg]:px-2.5",
        lg: "h-10 min-h-10 rounded-md px-6 has-[>svg]:px-4",
        icon: "size-9 min-h-9 rounded-md",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

function Button({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean;
  }) {
  const Comp = asChild ? Slot : "button";

  return (
    <Comp
      data-slot="button"
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  );
}

export { Button, buttonVariants };

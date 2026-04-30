import clsx from "clsx";

type Variant =
  | "gray" | "blue" | "green" | "yellow" | "red" | "purple" | "orange";

const variants: Record<Variant, string> = {
  gray:   "bg-gray-100 text-gray-700",
  blue:   "bg-blue-100 text-blue-700",
  green:  "bg-green-100 text-green-700",
  yellow: "bg-yellow-100 text-yellow-700",
  red:    "bg-red-100 text-red-700",
  purple: "bg-purple-100 text-purple-700",
  orange: "bg-orange-100 text-orange-700",
};

interface BadgeProps {
  children: React.ReactNode;
  variant?: Variant;
  className?: string;
}

export function Badge({ children, variant = "gray", className }: BadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        variants[variant],
        className
      )}
    >
      {children}
    </span>
  );
}

// 도메인별 헬퍼
export function SeverityBadge({ severity }: { severity: string }) {
  const map: Record<string, Variant> = {
    low: "green", medium: "yellow", high: "orange", critical: "red",
  };
  return <Badge variant={map[severity] ?? "gray"}>{severity}</Badge>;
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, Variant> = {
    active: "green", deprecated: "yellow", retired: "gray",
    open: "blue", diagnosing: "purple", pending_approval: "orange",
    executing: "yellow", resolved: "green",
    pending: "gray", running: "blue", completed: "green", failed: "red",
  };
  return <Badge variant={map[status] ?? "gray"}>{status}</Badge>;
}

import clsx from "clsx";

interface StatsCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  trend?: { value: number; label: string };
  icon?: React.ReactNode;
  color?: "blue" | "green" | "yellow" | "red" | "purple";
}

const colors = {
  blue:   { bg: "bg-blue-50",   icon: "text-blue-600",   badge: "bg-blue-100 text-blue-700" },
  green:  { bg: "bg-green-50",  icon: "text-green-600",  badge: "bg-green-100 text-green-700" },
  yellow: { bg: "bg-yellow-50", icon: "text-yellow-600", badge: "bg-yellow-100 text-yellow-700" },
  red:    { bg: "bg-red-50",    icon: "text-red-600",    badge: "bg-red-100 text-red-700" },
  purple: { bg: "bg-purple-50", icon: "text-purple-600", badge: "bg-purple-100 text-purple-700" },
};

export function StatsCard({
  title,
  value,
  subtitle,
  trend,
  icon,
  color = "blue",
}: StatsCardProps) {
  const c = colors[color];
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-500">{title}</p>
          <p className="mt-2 text-2xl font-bold text-gray-900">{value}</p>
          {subtitle && <p className="mt-1 text-xs text-gray-400">{subtitle}</p>}
          {trend && (
            <div className={clsx("mt-2 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium", c.badge)}>
              <span>{trend.value >= 0 ? "↑" : "↓"} {Math.abs(trend.value)}%</span>
              <span className="text-gray-500">{trend.label}</span>
            </div>
          )}
        </div>
        {icon && (
          <div className={clsx("flex h-10 w-10 items-center justify-center rounded-lg", c.bg, c.icon)}>
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}

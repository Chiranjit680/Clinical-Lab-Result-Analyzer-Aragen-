const SEVERITY = {
  critical: { label: "Critical", icon: "🚨", className: "badge badge--critical" },
  warning: { label: "Warning", icon: "⚠️", className: "badge badge--warning" },
  normal: { label: "Normal", icon: "✓", className: "badge badge--normal" },
  unknown: { label: "Unknown", icon: "?", className: "badge badge--unknown" },
};

export function severityKey(status) {
  const key = String(status || "unknown").toLowerCase();
  return SEVERITY[key] ? key : "unknown";
}

export default function SeverityBadge({ status }) {
  const { label, icon, className } = SEVERITY[severityKey(status)];
  return (
    <span className={className}>
      <span aria-hidden="true">{icon}</span>
      {label}
    </span>
  );
}

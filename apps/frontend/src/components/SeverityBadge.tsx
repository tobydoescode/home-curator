import { Badge } from "@mantine/core";

type Severity = "info" | "warning" | "error";

const COLORS: Record<Severity, string> = {
  info: "violet",
  warning: "yellow",
  error: "red",
};

export function SeverityBadge({
  severity,
  count,
}: {
  severity: Severity;
  count: number;
}) {
  return (
    <Badge color={COLORS[severity]} variant="light" radius="xl">
      {count}
    </Badge>
  );
}

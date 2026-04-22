import { Stack, Title } from "@mantine/core";

import type { PoliciesFileShape } from "@/hooks/usePolicies";

export interface SectionProps {
  draft: PoliciesFileShape;
  onChange: (d: PoliciesFileShape) => void;
}

export function NamingSection({ draft: _draft, onChange: _onChange }: SectionProps) {
  return (
    <Stack>
      <Title order={4}>Naming</Title>
    </Stack>
  );
}

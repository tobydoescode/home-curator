import { Stack, Title } from "@mantine/core";

import type { SectionProps } from "./NamingSection";

export function CustomRulesSection({ draft: _draft, onChange: _onChange }: SectionProps) {
  return (
    <Stack>
      <Title order={4}>Custom Rules</Title>
    </Stack>
  );
}

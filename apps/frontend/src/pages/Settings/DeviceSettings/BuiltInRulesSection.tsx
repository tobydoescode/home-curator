import { Stack, Title } from "@mantine/core";

import type { SectionProps } from "./NamingSection";

export function BuiltInRulesSection({ draft: _draft, onChange: _onChange }: SectionProps) {
  return (
    <Stack>
      <Title order={4}>Built-In Rules</Title>
    </Stack>
  );
}

import { Alert, Stack, Title } from "@mantine/core";

export function EntitySettingsPage() {
  return (
    <Stack>
      <Title order={3}>Entity Settings</Title>
      <Alert color="gray" variant="light" title="Coming Soon">
        Entity policies will be editable here once the Entities view ships. Until then, this page is a placeholder.
      </Alert>
    </Stack>
  );
}

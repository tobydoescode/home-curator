import { Alert, Button, Group, Loader, Stack, Title } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useEffect, useState } from "react";

import { usePoliciesFile, useUpdatePolicies, type PoliciesFileShape } from "@/hooks/usePolicies";
import { BuiltInRulesSection } from "./BuiltInRulesSection";
import { CustomRulesSection } from "./CustomRulesSection";
import { NamingSection } from "./NamingSection";

export function DeviceSettingsPage() {
  const { data, isLoading, error } = usePoliciesFile();
  const update = useUpdatePolicies();
  const [draft, setDraft] = useState<PoliciesFileShape | null>(null);

  useEffect(() => {
    if (data) setDraft(structuredClone(data));
  }, [data]);

  if (isLoading || draft === null) return <Loader />;
  if (error) {
    return <Alert color="red" title="Failed To Load Policies">{String(error)}</Alert>;
  }

  const save = async () => {
    try {
      await update.mutateAsync(draft);
      notifications.show({ color: "green", title: "Saved", message: "Device settings updated." });
    } catch (e) {
      notifications.show({ color: "red", title: "Save Failed", message: String(e) });
    }
  };

  return (
    <Stack gap="lg">
      <Title order={3}>Device Settings</Title>
      <NamingSection draft={draft} onChange={setDraft} />
      <BuiltInRulesSection draft={draft} onChange={setDraft} />
      <CustomRulesSection draft={draft} onChange={setDraft} />
      <Group justify="flex-end">
        <Button onClick={save} loading={update.isPending}>Save</Button>
      </Group>
    </Stack>
  );
}

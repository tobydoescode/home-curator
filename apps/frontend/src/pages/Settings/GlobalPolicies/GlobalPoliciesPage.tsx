import { Alert, Button, Grid, Loader, Stack, Title } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router";

import { useSimulate } from "@/hooks/useSimulate";
import { usePoliciesFile, useUpdatePolicies, type PoliciesFileShape } from "@/hooks/usePolicies";
import { applyCustomRuleEdit } from "@/pages/Settings/applyCustomRuleEdit";
import { CustomRuleEditor, type CustomRule } from "@/pages/Settings/CustomRuleEditor";
import { Simulator, type SimulateResponse } from "@/pages/Settings/Simulator";
import { CustomRulesList } from "./CustomRulesList";

export function GlobalPoliciesPage() {
  const { data, isLoading, error } = usePoliciesFile();
  const update = useUpdatePolicies();
  const simulate = useSimulate();
  const [draft, setDraft] = useState<PoliciesFileShape | null>(null);
  const [editing, setEditing] = useState<number | "new" | null>(null);
  const [simResult, setSimResult] = useState<SimulateResponse | null>(null);
  const [params] = useSearchParams();

  useEffect(() => {
    if (data) setDraft(structuredClone(data));
  }, [data]);

  useEffect(() => {
    const id = params.get("test");
    if (!id || !draft) return;
    (async () => {
      const res = await simulate.mutateAsync({ policy_id: id } as any);
      setSimResult(res);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params, draft]);

  if (isLoading || draft === null) return <Loader />;
  if (error) return <Alert color="red" title="Failed To Load Policies">{String(error)}</Alert>;

  async function save() {
    try {
      await update.mutateAsync(draft!);
      notifications.show({ color: "green", title: "Saved", message: "Global policies updated." });
    } catch (e) {
      notifications.show({ color: "red", title: "Save Failed", message: String(e) });
    }
  }

  async function handleTest(index: number) {
    const rule = draft!.policies[index];
    const res = await simulate.mutateAsync({ policy: rule as any });
    setSimResult(res);
  }

  function handleSaved(rule: CustomRule, slot: number | "new") {
    setDraft(applyCustomRuleEdit(draft!, rule, slot));
    setEditing(null);
  }

  return (
    <Stack>
      <Title order={3}>Global Policies</Title>
      <Grid>
        <Grid.Col span={{ base: 12, md: 6 }}>
          <CustomRulesList
            draft={draft}
            onChange={setDraft}
            onEdit={setEditing}
            onAdd={() => setEditing("new")}
            onTest={handleTest}
          />
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 6 }}>
          <Simulator result={simResult} />
        </Grid.Col>
      </Grid>
      <Button onClick={save} loading={update.isPending}>Save</Button>
      {editing !== null && (
        <CustomRuleEditor
          initial={editing === "new" ? null : (draft.policies[editing] as any)}
          onClose={() => setEditing(null)}
          onSaved={(rule) => handleSaved(rule, editing)}
        />
      )}
    </Stack>
  );
}

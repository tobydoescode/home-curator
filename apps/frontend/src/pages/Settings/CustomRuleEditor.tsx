import { Alert, Button, Drawer, Group, Select, Stack, Switch, TextInput, Textarea, Title } from "@mantine/core";
import { useEffect, useState } from "react";

import { useCompile } from "@/hooks/useCompile";
import { useSimulate } from "@/hooks/useSimulate";
import { type SimulateResponse } from "@/pages/Settings/Simulator";

export interface CustomRule {
  id: string;
  type: "custom";
  scope: "devices";
  enabled: boolean;
  severity: "info" | "warning" | "error";
  when: string;
  assert: string;
  message: string;
}

export interface CustomRuleEditorProps {
  initial: CustomRule | null;
  onClose: () => void;
  onSaved: (rule: CustomRule) => void;
}

const SEVERITIES = ["info", "warning", "error"] as const;

function slug(name: string): string {
  return name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") || "rule";
}

export function CustomRuleEditor({ initial, onClose, onSaved }: CustomRuleEditorProps) {
  const [name, setName] = useState(initial?.id ?? "");
  const [severity, setSeverity] = useState<CustomRule["severity"]>(initial?.severity ?? "info");
  const [enabled, setEnabled] = useState(initial?.enabled ?? true);
  const [whenText, setWhenText] = useState(initial?.when ?? "true");
  const [assertText, setAssertText] = useState(initial?.assert ?? "");
  const [message, setMessage] = useState(initial?.message ?? "");
  const [compileErr, setCompileErr] = useState<string | null>(null);
  const compile = useCompile();
  const simulate = useSimulate();
  const [simResult, setSimResult] = useState<SimulateResponse | null>(null);

  useEffect(() => {
    const h = setTimeout(async () => {
      if (!assertText.trim()) {
        setCompileErr(null);
        return;
      }
      try {
        const res = await compile.mutateAsync(buildRule() as any);
        setCompileErr(res.ok ? null : res.error ?? "Unknown compile error");
      } catch (e) {
        setCompileErr(String(e));
      }
    }, 300);
    return () => clearTimeout(h);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [whenText, assertText, message, severity, enabled, name]);

  function buildRule(): CustomRule {
    return {
      id: initial?.id ?? slug(name),
      type: "custom",
      scope: "devices",
      enabled,
      severity,
      when: whenText,
      assert: assertText,
      message,
    };
  }

  async function runTest() {
    const res = await simulate.mutateAsync({ policy: buildRule() as any });
    setSimResult(res);
  }

  return (
    <Drawer opened onClose={onClose} position="right" size="xl">
      <Stack>
        <Title order={4}>{initial ? "Edit Custom Rule" : "Add Custom Rule"}</Title>
        <TextInput
          label="Name"
          aria-label="Name"
          value={name}
          onChange={(e) => setName(e.currentTarget.value)}
          disabled={!!initial}
          description={initial ? "ID is immutable after first save." : "ID is the slug of this name."}
        />
        <Group>
          <Select
            label="Severity"
            aria-label="Severity"
            data={SEVERITIES.map((s) => ({ value: s, label: s[0].toUpperCase() + s.slice(1) }))}
            value={severity}
            onChange={(v) => v && setSeverity(v as CustomRule["severity"])}
          />
          <Switch label="Enabled" checked={enabled} onChange={(e) => setEnabled(e.currentTarget.checked)} />
        </Group>
        <Textarea
          label="When"
          aria-label="When"
          description="Gate — only devices matching this are evaluated. Default: true"
          autosize
          minRows={4}
          styles={{ input: { fontFamily: "monospace" } }}
          value={whenText}
          onChange={(e) => setWhenText(e.currentTarget.value)}
        />
        <Textarea
          label="Assert"
          aria-label="Assert"
          description="If this evaluates false for an applicable device, the issue is emitted."
          autosize
          minRows={4}
          styles={{ input: { fontFamily: "monospace" } }}
          value={assertText}
          onChange={(e) => setAssertText(e.currentTarget.value)}
        />
        <Textarea
          label="Message"
          aria-label="Message"
          description="Shown in the Issue Panel."
          autosize
          minRows={2}
          value={message}
          onChange={(e) => setMessage(e.currentTarget.value)}
        />
        {compileErr && <Alert color="red" title="Compile Error">{compileErr}</Alert>}
        {simResult && simResult.ok && simResult.counts && (
          <Alert color="blue" title="Simulation">
            Matched when: {simResult.counts.matched_when} · Passes: {simResult.counts.passes_assert}
            {" "}· Fails: {simResult.counts.fails_assert} · Errored: {simResult.counts.errored}
          </Alert>
        )}
        <Group justify="flex-end">
          <Button variant="default" onClick={runTest} loading={simulate.isPending}>Test</Button>
          <Button onClick={() => onSaved(buildRule())} disabled={!!compileErr || !assertText.trim()}>Save</Button>
        </Group>
      </Stack>
    </Drawer>
  );
}

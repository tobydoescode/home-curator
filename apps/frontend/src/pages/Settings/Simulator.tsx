import { Accordion, Alert, Stack, Text, Title } from "@mantine/core";

import type { components } from "@/api/generated";

export type SimulateResponse = components["schemas"]["SimulateResponse"];

export interface SimulatorProps {
  result: SimulateResponse | null;
}

export function Simulator({ result }: SimulatorProps) {
  if (!result) return <Text c="dimmed">Pick a rule to test.</Text>;
  if (!result.ok) {
    return <Alert color="red" title="Parse Error">{result.error}</Alert>;
  }
  const c = result.counts!;
  return (
    <Stack>
      <Title order={5}>Results</Title>
      <Text>
        Matched when: {c.matched_when} · Passes: {c.passes_assert} · Fails: {c.fails_assert} · Errored: {c.errored}
      </Text>
      <Accordion multiple defaultValue={["failing", "errored"]} transitionDuration={0}>
        <Accordion.Item value="failing">
          <Accordion.Control>Failing ({result.failing!.length})</Accordion.Control>
          <Accordion.Panel>
            {result.failing!.map((r) => (
              <div key={r.id}>
                <strong>{r.name}</strong> · {r.room ?? "—"} — {r.message}
              </div>
            ))}
          </Accordion.Panel>
        </Accordion.Item>
        <Accordion.Item value="errored">
          <Accordion.Control>Errored ({result.errored!.length})</Accordion.Control>
          <Accordion.Panel>
            {result.errored!.map((r) => (
              <div key={r.id}>
                <strong>{r.name}</strong> — {r.error}
              </div>
            ))}
          </Accordion.Panel>
        </Accordion.Item>
        <Accordion.Item value="passing">
          <Accordion.Control>Passing ({result.passing!.length})</Accordion.Control>
          <Accordion.Panel>
            {result.passing!.map((r) => (
              <div key={r.id}>
                <strong>{r.name}</strong> · {r.room ?? "—"}
              </div>
            ))}
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>
    </Stack>
  );
}

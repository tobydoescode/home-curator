import { Drawer, Title } from "@mantine/core";

export interface CustomRuleEditorProps {
  initial: any | null;
  onClose: () => void;
  onSaved: (rule: any) => void;
}

export function CustomRuleEditor({ initial, onClose }: CustomRuleEditorProps) {
  return (
    <Drawer opened onClose={onClose} position="right" size="lg">
      <Title order={4}>{initial ? "Edit Custom Rule" : "Add Custom Rule"}</Title>
    </Drawer>
  );
}

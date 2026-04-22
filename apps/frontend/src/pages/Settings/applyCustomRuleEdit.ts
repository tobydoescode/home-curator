import type { CustomRule } from "@/pages/Settings/CustomRuleEditor";
import type { PoliciesFileShape } from "@/hooks/usePolicies";

/**
 * Merge an edited custom rule back into a policies draft.
 * `slot === "new"` appends the rule; an index replaces in place.
 */
export function applyCustomRuleEdit(
  draft: PoliciesFileShape,
  rule: CustomRule,
  slot: number | "new",
): PoliciesFileShape {
  const policies = [...draft.policies];
  if (slot === "new") policies.push(rule);
  else policies[slot] = rule;
  return { ...draft, policies };
}

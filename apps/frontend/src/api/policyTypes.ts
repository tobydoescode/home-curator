import type { components } from "./generated";

/**
 * Names and narrowing for the policy union.
 *
 * `PoliciesFile.policies` is a discriminated union over six rule types, and
 * the Settings pages work almost entirely with the `custom` member. Without a
 * guard, every access to a custom-only field needed an `as any`, which turned
 * off type checking for the whole expression rather than just the narrowing —
 * so a genuinely wrong field name would have gone unnoticed too.
 */

export type Policy = components["schemas"]["PoliciesFile"]["policies"][number];
export type CustomPolicy = components["schemas"]["CustomPolicy"];
export type PoliciesFile = components["schemas"]["PoliciesFile"];

export function isCustomPolicy(policy: Policy): policy is CustomPolicy {
  return policy.type === "custom";
}

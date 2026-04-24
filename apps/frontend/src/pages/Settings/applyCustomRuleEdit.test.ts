import { describe, expect, it } from "vitest";

import { applyCustomRuleEdit } from "./applyCustomRuleEdit";

const baseDraft = {
  policies: [
    {
      id: "one",
      type: "custom",
      scope: "device",
      when: "true",
      assert: "true",
      message: "One",
    },
  ],
};

describe("applyCustomRuleEdit", () => {
  it("appends a new custom rule without mutating the original draft", () => {
    const rule = {
      id: "two",
      type: "custom",
      scope: "device",
      when: "true",
      assert: "true",
      message: "Two",
    };
    const next = applyCustomRuleEdit(baseDraft as any, rule as any, "new");

    expect(next.policies).toHaveLength(2);
    expect(next.policies[1]).toBe(rule);
    expect(baseDraft.policies).toHaveLength(1);
  });

  it("replaces an existing custom rule without mutating the original policies array", () => {
    const rule = {
      id: "replacement",
      type: "custom",
      scope: "device",
      when: "true",
      assert: "true",
      message: "Replacement",
    };
    const next = applyCustomRuleEdit(baseDraft as any, rule as any, 0);

    expect(next.policies).toEqual([rule]);
    expect(next.policies).not.toBe(baseDraft.policies);
    expect(baseDraft.policies[0].id).toBe("one");
  });
});

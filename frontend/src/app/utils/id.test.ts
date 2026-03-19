import { describe, expect, it } from "vitest";

import { generateId, nowIso } from "./id";

describe("id utils", () => {
  it("generateId should include prefix", () => {
    const value = generateId("task");
    expect(value.startsWith("task_")).toBe(true);
  });

  it("nowIso should return valid ISO string", () => {
    const value = nowIso();
    expect(Number.isNaN(Date.parse(value))).toBe(false);
  });
});

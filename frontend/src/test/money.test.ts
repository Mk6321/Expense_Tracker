import { describe, expect, it } from "vitest";
import { formatMoney, previewEqualSplit, sum } from "../lib/money";

describe("formatMoney", () => {
  it("groups thousands and always shows two decimals", () => {
    expect(formatMoney("1234.5", "INR")).toBe("₹1,234.50");
    expect(formatMoney("1000000", "USD")).toBe("$1,000,000.00");
    expect(formatMoney("0", "INR")).toBe("₹0.00");
  });

  it("keeps the sign in front of the symbol", () => {
    expect(formatMoney("-42.5", "INR")).toBe("-₹42.50");
    expect(formatMoney("42.5", "INR", { signed: true })).toBe("+₹42.50");
    expect(formatMoney("-42.5", "INR", { absolute: true })).toBe("₹42.50");
  });

  it("does not lose cents the way float maths would", () => {
    // 0.1 + 0.2 is the canonical float failure; decimal.js gets it right.
    expect(sum(["0.1", "0.2"]).toFixed(2)).toBe("0.30");
    expect(formatMoney(sum(["33.34", "33.33", "33.33"]), "INR")).toBe("₹100.00");
  });
});

describe("previewEqualSplit", () => {
  it("sums to the total and matches the server's tiebreak", () => {
    const split = previewEqualSplit("100.00", [3, 1, 2]);
    // Remainders all tie, so the extra cent goes to the lowest user_id.
    expect(split.get(1)).toBe("33.34");
    expect(split.get(2)).toBe("33.33");
    expect(split.get(3)).toBe("33.33");
    expect(sum([...split.values()]).toFixed(2)).toBe("100.00");
  });

  it("is independent of the order the ids arrive in", () => {
    const forward = previewEqualSplit("10.00", [1, 2, 3]);
    const backward = previewEqualSplit("10.00", [3, 2, 1]);
    expect([...forward.entries()].sort()).toEqual([...backward.entries()].sort());
  });

  it("handles a six-way split without dropping a cent", () => {
    const split = previewEqualSplit("100.00", [1, 2, 3, 4, 5, 6]);
    expect(sum([...split.values()]).toFixed(2)).toBe("100.00");
  });
});

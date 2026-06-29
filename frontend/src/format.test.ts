import { describe, expect, it } from "vitest";
import { eur, siteName } from "./format";

describe("format helpers", () => {
  it("formats euros to two decimals", () => {
    expect(eur(11.4)).toBe("€11.40");
    expect(eur(0)).toBe("€0.00");
  });

  it("resolves site names, falling back when unknown", () => {
    const sites = [{ id: 1, name: "Centro" }, { id: 2, name: "Barrio" }];
    expect(siteName(sites, 2)).toBe("Barrio");
    expect(siteName(sites, 9)).toBe("Site 9");
  });
});

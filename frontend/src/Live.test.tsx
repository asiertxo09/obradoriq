import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import type { IntradaySignalOut } from "./api";

const bakeMore: IntradaySignalOut = {
  product_id: 1,
  product_name: "Croissant",
  site_id: 10,
  site_name: "Centro",
  as_of: "2026-06-29T12:00:00",
  sold_so_far: 60,
  on_hand: 12,
  projected_demand: 95,
  projected_sellout_time: "16:30:00",
  action: "bake_more",
  action_qty: 24,
  from_site_id: null,
  from_site_name: null,
  eur_at_risk: 41.5,
  confidence: "HIGH",
  reason: "Selling faster than stock; par-bake now to avoid a 16:30 stockout.",
};

const hold: IntradaySignalOut = {
  product_id: 2,
  product_name: "Baguette",
  site_id: 10,
  site_name: "Centro",
  as_of: "2026-06-29T12:00:00",
  sold_so_far: 30,
  on_hand: 40,
  projected_demand: 55,
  projected_sellout_time: null,
  action: "hold",
  action_qty: 0,
  from_site_id: null,
  from_site_name: null,
  eur_at_risk: 0,
  confidence: "MEDIUM",
  reason: "On pace.",
};

const getIntraday = vi.fn(async (_asOf: string) => [bakeMore, hold]);

vi.mock("./api", () => ({
  api: { getIntraday: (asOf: string) => getIntraday(asOf) },
}));

import Live from "./Live";

describe("Live tab", () => {
  it("renders the bake_more action card with € at risk and summarizes the hold", async () => {
    render(<Live />);

    // The action card for the bake_more signal renders with its title and € at risk.
    await waitFor(() => {
      expect(screen.getByText("Bake 24 more Croissant")).toBeTruthy();
    });
    const card = screen.getByText("Bake 24 more Croissant").closest(".live-action")! as HTMLElement;
    expect(within(card).getByText("€41.50")).toBeTruthy();

    // The hold signal does NOT get an action card — it is summarized in the site table.
    expect(screen.queryByText(/Baguette/i)).toBeTruthy();
    const row = screen.getByText("Baguette").closest("tr")!;
    expect(within(row).getByText("on track")).toBeTruthy();

    // Backend was queried for an as_of on the intraday day.
    expect(getIntraday).toHaveBeenCalled();
    expect(String(getIntraday.mock.calls[0][0])).toContain("2026-06-28");
  });
});

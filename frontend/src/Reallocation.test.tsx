import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { Reallocation, Site } from "./api";

const item: Reallocation = {
  id: 42,
  product_name: "Almond Croissant",
  from_site_id: 2,
  to_site_id: 1,
  quantity: 6,
  eur_waste_avoided: 5.7,
  justification: "Shift 6 of Almond Croissant's planned production from Barrio to Centro.",
};
const sites: Site[] = [
  { id: 1, name: "Centro", location: "Gran Vía 28, Madrid" },
  { id: 2, name: "Barrio", location: "Calle de Bravo Murillo 110, Madrid" },
];

const reallocations = vi.fn(async (_date: string) => [item]);
const decideReallocation = vi.fn(async (_id: number, _decision: string) => ({ status: "logged" }));

vi.mock("./api", () => ({
  api: {
    reallocations: (date: string) => reallocations(date),
    decideReallocation: (id: number, decision: string) => decideReallocation(id, decision),
  },
}));

import { ReallocationView } from "./App";

afterEach(() => {
  cleanup();
  reallocations.mockClear();
  decideReallocation.mockClear();
});

describe("ReallocationView", () => {
  it("approving calls the API and shows an Approved status", async () => {
    render(<ReallocationView sites={sites} />);

    await waitFor(() => expect(screen.getByText("Approve")).toBeTruthy());
    fireEvent.click(screen.getByText("Approve"));

    expect(decideReallocation).toHaveBeenCalledWith(42, "accepted");
    await waitFor(() => expect(screen.getByText("Approved")).toBeTruthy());
    expect(screen.queryByText("Approve")).toBeNull();
    expect(screen.queryByText("Dismiss")).toBeNull();
  });

  it("dismissing calls the API and shows a Dismissed status", async () => {
    render(<ReallocationView sites={sites} />);

    await waitFor(() => expect(screen.getByText("Dismiss")).toBeTruthy());
    fireEvent.click(screen.getByText("Dismiss"));

    expect(decideReallocation).toHaveBeenCalledWith(42, "dismissed");
    await waitFor(() => expect(screen.getByText("Dismissed")).toBeTruthy());
  });
});

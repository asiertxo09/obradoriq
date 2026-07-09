import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import Landing from "./Landing";

afterEach(cleanup);

describe("Landing", () => {
  it("renders the hero with the value proposition and demo hint", () => {
    render(<Landing onEnter={vi.fn()} />);

    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain(
      "Stop baking money into the bin."
    );
    expect(screen.getByText(/owner@obradoriq\.demo/)).toBeTruthy();
  });

  it("calls onEnter from the hero CTA", () => {
    const onEnter = vi.fn();
    render(<Landing onEnter={onEnter} />);

    fireEvent.click(screen.getByText("Try the live demo"));
    expect(onEnter).toHaveBeenCalledTimes(1);
  });

  it("calls onEnter from the header Sign in and the final CTA", () => {
    const onEnter = vi.fn();
    render(<Landing onEnter={onEnter} />);

    fireEvent.click(screen.getByText("Sign in"));
    fireEvent.click(screen.getByText("Open the live demo"));
    expect(onEnter).toHaveBeenCalledTimes(2);
  });

  it("shows the backtest stats and the four how-it-works steps", () => {
    render(<Landing onEnter={vi.fn()} />);

    expect(screen.getByText("+€997")).toBeTruthy();
    expect(screen.getByText("−11%")).toBeTruthy();
    expect(screen.getByText("€1,154")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "You decide" })).toBeTruthy();
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import Tour, { TOUR_STEPS } from "./Tour";

afterEach(cleanup);

describe("Tour", () => {
  it("opens on the first step and switches to that step's tab", () => {
    const onNavigate = vi.fn();
    render(<Tour onNavigate={onNavigate} onClose={vi.fn()} />);

    expect(screen.getByText(`Step 1 of ${TOUR_STEPS.length}`)).toBeTruthy();
    expect(screen.getByText(TOUR_STEPS[0].title)).toBeTruthy();
    expect(onNavigate).toHaveBeenCalledWith(TOUR_STEPS[0].tab);
    // First step has no Back button.
    expect(screen.queryByText("Back")).toBeNull();
  });

  it("advances to the next step and navigates to its tab", () => {
    const onNavigate = vi.fn();
    render(<Tour onNavigate={onNavigate} onClose={vi.fn()} />);

    fireEvent.click(screen.getByText("Next"));

    expect(screen.getByText(`Step 2 of ${TOUR_STEPS.length}`)).toBeTruthy();
    expect(screen.getByText(TOUR_STEPS[1].title)).toBeTruthy();
    expect(onNavigate).toHaveBeenLastCalledWith(TOUR_STEPS[1].tab);
  });

  it("goes back to the previous step", () => {
    render(<Tour onNavigate={vi.fn()} onClose={vi.fn()} />);

    fireEvent.click(screen.getByText("Next"));
    fireEvent.click(screen.getByText("Back"));

    expect(screen.getByText(`Step 1 of ${TOUR_STEPS.length}`)).toBeTruthy();
  });

  it("shows Finish instead of Next on the last step, and calls onClose", () => {
    const onClose = vi.fn();
    render(<Tour onNavigate={vi.fn()} onClose={onClose} />);

    for (let i = 1; i < TOUR_STEPS.length; i++) {
      fireEvent.click(screen.getByText("Next"));
    }

    expect(screen.getByText(`Step ${TOUR_STEPS.length} of ${TOUR_STEPS.length}`)).toBeTruthy();
    expect(screen.queryByText("Next")).toBeNull();
    fireEvent.click(screen.getByText("Finish"));
    expect(onClose).toHaveBeenCalled();
  });

  it("calls onClose when Skip tour is clicked", () => {
    const onClose = vi.fn();
    render(<Tour onNavigate={vi.fn()} onClose={onClose} />);

    fireEvent.click(screen.getByText("Skip tour"));
    expect(onClose).toHaveBeenCalled();
  });
});

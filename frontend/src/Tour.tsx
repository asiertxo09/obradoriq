import { useEffect, useState } from "react";

export type TabId = "ask" | "live" | "plan" | "realloc" | "weekly";

export interface TourStep {
  tab: TabId;
  title: string;
  body: string;
}

export const TOUR_STEPS: TourStep[] = [
  {
    tab: "ask",
    title: "Ask ObradorIQ",
    body: "Plain-language questions to your operations advisor. It calls the forecasting " +
      "and reallocation tools and answers with grounded numbers — mention a festival or a " +
      "heatwave and it adjusts the plan.",
  },
  {
    tab: "live",
    title: "Live — the intraday plan",
    body: "A running pace-curve projection through the day: bake more, move stock between " +
      "shops, or mark down, before you actually sell out or over-produce.",
  },
  {
    tab: "plan",
    title: "Daily plan",
    body: "Tomorrow's bake list per shop and product, with a confidence flag on each. " +
      "\"Print plan\" turns it into a sheet for the bakery wall.",
  },
  {
    tab: "realloc",
    title: "Reallocation",
    body: "The differentiator for a multi-site chain: when one shop chronically over-bakes " +
      "a product another sells out of, ObradorIQ suggests shifting planned production " +
      "between them — no goods moved, no extra baking.",
  },
  {
    tab: "weekly",
    title: "Weekly review",
    body: "Total waste, euros recoverable, and \"True Margin\" — profit after waste is " +
      "counted, product by product.",
  },
];

export default function Tour({
  onNavigate,
  onClose,
}: {
  onNavigate: (tab: TabId) => void;
  onClose: () => void;
}) {
  const [step, setStep] = useState(0);
  const current = TOUR_STEPS[step];
  const isFirst = step === 0;
  const isLast = step === TOUR_STEPS.length - 1;

  useEffect(() => {
    onNavigate(current.tab);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  return (
    <div className="tour-overlay" role="dialog" aria-label="Guided tour">
      <div className="tour-card">
        <div className="tour-head">
          <span className="tour-progress">Step {step + 1} of {TOUR_STEPS.length}</span>
          <button className="tour-close" aria-label="Close tour" onClick={onClose}>×</button>
        </div>
        <div className="tour-title">{current.title}</div>
        <p className="tour-body">{current.body}</p>
        <div className="tour-actions">
          <button className="ghost" onClick={onClose}>Skip tour</button>
          <div>
            {!isFirst && (
              <button className="ghost" onClick={() => setStep((s) => s - 1)}>Back</button>
            )}
            {!isLast && (
              <button className="primary" onClick={() => setStep((s) => s + 1)}>Next</button>
            )}
            {isLast && (
              <button className="primary" onClick={onClose}>Finish</button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

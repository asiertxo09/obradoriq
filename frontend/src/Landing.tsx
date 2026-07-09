interface LandingProps {
  onEnter: () => void;
}

const STATS = [
  {
    value: "+€997",
    label: "Profit recovered vs the bakery's own planning",
    detail: "Walk-forward backtest, demo chain",
  },
  {
    value: "−11%",
    label: "Waste vs the same baseline",
    detail: "832 units instead of 933",
  },
  {
    value: "€1,154",
    label: "Recovered by one 11:00 intraday check-in",
    detail: "Across the chain, vs doing nothing",
  },
];

const STEPS = [
  {
    title: "Share your numbers",
    body:
      "Each shop uploads daily sales and end-of-day waste — a CSV or POS export is enough. " +
      "ObradorIQ tags every day with the real weather and holiday calendar automatically.",
  },
  {
    title: "Get your morning bake plan",
    body:
      "Per shop and per product: how much to bake, at the profit-optimal level for each item's " +
      "margin — high-margin croissants keep a buffer, low-margin loaves hug the forecast. " +
      "Every suggestion is framed in euros of waste avoided.",
  },
  {
    title: "Rebalance the chain",
    body:
      "When one shop chronically over-bakes what another sells out of, ObradorIQ suggests " +
      "shifting planned production between them — the cross-site view no single-shop tool " +
      "and no solo bakery has.",
  },
  {
    title: "You decide",
    body:
      "Accept, edit, or dismiss every suggestion; every decision is logged. The weekly review " +
      "shows total waste and your true margin — profit after what went in the bin.",
  },
];

const FEATURES = [
  {
    title: "Daily production plan",
    body: "A printable per-shop bake sheet every morning, with forecast, quantity, leftover risk and a confidence flag on each line.",
  },
  {
    title: "Cross-site reallocation",
    body: "Spots the shop that over-bakes what its sibling sells out of, and proposes the shift in euros recovered.",
  },
  {
    title: "Ask ObradorIQ",
    body: "Plain-language questions, grounded answers. Tell it about the street festival on Saturday and the plan adjusts — with the bump attributed, not invented.",
  },
  {
    title: "Live intraday plan",
    body: "By mid-morning it knows which products are running hot or cold and suggests bake-more, move, or markdown before the day is lost.",
  },
  {
    title: "Weekly true margin",
    body: "Naïve margin says the croissant earns 68%. True margin says what's left after waste — and where the money is actually leaking.",
  },
];

export default function Landing({ onEnter }: LandingProps) {
  return (
    <div className="landing">
      <header className="ld-top">
        <div className="brand">
          Obrador<span>IQ</span>
        </div>
        <nav className="ld-nav" aria-label="Page sections">
          <a href="#how">How it works</a>
          <a href="#features">What you get</a>
          <a href="#results">Results</a>
          <button className="ghost" onClick={onEnter}>
            Sign in
          </button>
        </nav>
      </header>

      <main>
        <section className="ld-hero" aria-labelledby="ld-hero-title">
          <p className="ld-kicker">Produce smarter. Sell better. Waste less.</p>
          <h1 id="ld-hero-title">Stop baking money into the bin.</h1>
          <p className="ld-sub">
            ObradorIQ is the AI operations partner for small bakery chains of 2–4 shops. Every
            morning it tells each shop how much of every product to bake, spots when one shop
            over-bakes what another sells out of, and answers your questions in plain language.
            You always make the final call.
          </p>
          <div className="ld-cta-row">
            <button className="primary ld-cta" onClick={onEnter}>
              Try the live demo
            </button>
            <a className="ld-link" href="#how">
              See how it works
            </a>
          </div>
          <p className="muted ld-hint">
            Demo login: owner@obradoriq.demo / bakery123 — a two-shop Madrid chain, seeded and
            ready.
          </p>
        </section>

        <section id="results" className="ld-stats-band" aria-labelledby="ld-stats-title">
          <h2 id="ld-stats-title" className="ld-visually-hidden">
            Backtest results
          </h2>
          <div className="ld-stats">
            {STATS.map((s) => (
              <div key={s.value} className="ld-stat card">
                <div className="ld-stat-value">{s.value}</div>
                <div className="ld-stat-label">{s.label}</div>
                <div className="ld-stat-detail muted">{s.detail}</div>
              </div>
            ))}
          </div>
          <p className="ld-footnote muted">
            Walk-forward backtest against true demand on the demo chain: two shops on real Madrid
            streets, demand driven by real Madrid weather and holidays. On rainy and holiday days,
            the weather signal cuts forecast error from 19.8% to 17.4%.
          </p>
        </section>

        <section id="how" className="ld-section" aria-labelledby="ld-how-title">
          <h2 id="ld-how-title">How it works</h2>
          <ol className="ld-steps">
            {STEPS.map((s, i) => (
              <li key={s.title} className="ld-step">
                <div className="ld-step-num" aria-hidden="true">
                  {i + 1}
                </div>
                <div>
                  <h3>{s.title}</h3>
                  <p>{s.body}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>

        <section id="features" className="ld-section" aria-labelledby="ld-features-title">
          <h2 id="ld-features-title">Everything the owner needs — nothing a baker won't use</h2>
          <div className="ld-features">
            {FEATURES.map((f) => (
              <div key={f.title} className="card ld-feature">
                <h3>{f.title}</h3>
                <p>{f.body}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="ld-section ld-trust" aria-labelledby="ld-trust-title">
          <h2 id="ld-trust-title">Numbers you can trust</h2>
          <p>
            One rule makes ObradorIQ different from a chatbot with opinions:{" "}
            <strong>the math computes every number; the AI only phrases them.</strong> Forecasts,
            bake quantities and reallocations come from a deterministic recommender core. The
            language model writes them in your voice — and if it alters or invents a figure, the
            output is rejected and the grounded text is shown instead. Every recommendation is
            confidence-scored and audit-logged.
          </p>
        </section>

        <section className="ld-final" aria-labelledby="ld-final-title">
          <h2 id="ld-final-title">See your chain the way ObradorIQ does</h2>
          <p>
            Two minutes in the demo: a morning bake plan, a cross-site reallocation, and a live
            11:00 check-in.
          </p>
          <button className="ld-final-cta" onClick={onEnter}>
            Open the live demo
          </button>
        </section>
      </main>

      <footer className="ld-footer">
        <div className="brand">
          Obrador<span>IQ</span>
        </div>
        <p className="muted">Built for small bakery chains — starting in Madrid.</p>
      </footer>
    </div>
  );
}

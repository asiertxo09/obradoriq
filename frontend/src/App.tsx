import { useEffect, useState } from "react";
import {
  api,
  ChatTurn,
  clearToken,
  getToken,
  setToken,
  Reallocation,
  Recommendation,
  Site,
  ToolResult,
  Weekly,
} from "./api";
import { eur, siteName } from "./format";
import Landing from "./Landing";
import Live from "./Live";
import Tour, { TabId } from "./Tour";

const TOUR_SEEN_KEY = "obradoriq_tour_seen";

const DAILY_DATE = "2026-06-29";
const WEEK_END = "2026-06-28";

export default function App() {
  const [authed, setAuthed] = useState<boolean>(!!getToken());
  const [entering, setEntering] = useState(false);
  if (authed) return <Dashboard onLogout={() => { clearToken(); setAuthed(false); }} />;
  if (!entering) return <Landing onEnter={() => setEntering(true)} />;
  return <Login onLogin={() => setAuthed(true)} onBack={() => setEntering(false)} />;
}

function Login({ onLogin, onBack }: { onLogin: () => void; onBack: () => void }) {
  const [email, setEmail] = useState("owner@obradoriq.demo");
  const [password, setPassword] = useState("bakery123");
  const [err, setErr] = useState("");
  async function submit() {
    try {
      const r = await api.login(email, password);
      setToken(r.access_token);
      onLogin();
    } catch (e: any) {
      setErr("Login failed — check the demo credentials.");
    }
  }
  return (
    <div className="app">
      <div className="login card">
        <div className="brand">Obrador<span>IQ</span></div>
        <p className="tagline">Produce smarter. Sell better. Waste less.</p>
        <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email" />
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="password" />
        <button className="primary" onClick={submit}>Sign in</button>
        {err && <p className="err">{err}</p>}
        <p className="muted" style={{ fontSize: 12, marginTop: 12 }}>
          Demo: owner@obradoriq.demo / bakery123
        </p>
        <button className="ghost" onClick={onBack}>← Back</button>
      </div>
    </div>
  );
}

function HeroBanner() {
  const [w, setW] = useState<Weekly | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.weekly(WEEK_END)
      .then((data: Weekly) => { setW(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);
  if (loading) return <div className="hero-skeleton" />;
  if (!w) return null;
  return (
    <div className="hero">
      <div className="hero-main">{eur(w.eur_avoided_estimate)}</div>
      <div className="hero-label">Waste avoided this week</div>
      <div className="hero-sub">{w.week_start} → {w.week_end}</div>
      <div className="hero-secondary">{eur(w.total_waste_eur)} total waste tracked</div>
    </div>
  );
}

function Dashboard({ onLogout }: { onLogout: () => void }) {
  const [tab, setTab] = useState<TabId>("ask");
  const [sites, setSites] = useState<Site[]>([]);
  const [tourOpen, setTourOpen] = useState(() => {
    try {
      return !localStorage.getItem(TOUR_SEEN_KEY);
    } catch {
      return false;
    }
  });
  useEffect(() => { api.sites().then(setSites).catch(() => {}); }, []);

  function closeTour() {
    setTourOpen(false);
    try {
      localStorage.setItem(TOUR_SEEN_KEY, "1");
    } catch {
      // localStorage unavailable (e.g. private browsing) — tour just won't persist as "seen"
    }
  }

  return (
    <div className="app">
      <header className="top">
        <div className="brand">Obrador<span>IQ</span></div>
        <div>
          <button className="ghost" onClick={() => setTourOpen(true)}>Take the tour</button>
          <button className="ghost" onClick={onLogout}>Sign out</button>
        </div>
      </header>
      <HeroBanner />
      <div className="tabs">
        <div className={`tab ${tab === "ask" ? "active" : ""}`} onClick={() => setTab("ask")}>Ask ObradorIQ</div>
        <div className={`tab ${tab === "live" ? "active" : ""}`} onClick={() => setTab("live")}>Live</div>
        <div className={`tab ${tab === "plan" ? "active" : ""}`} onClick={() => setTab("plan")}>Daily plan</div>
        <div className={`tab ${tab === "realloc" ? "active" : ""}`} onClick={() => setTab("realloc")}>Reallocation</div>
        <div className={`tab ${tab === "weekly" ? "active" : ""}`} onClick={() => setTab("weekly")}>Weekly review</div>
      </div>
      {tab === "ask" && <AskView />}
      {tab === "live" && <Live />}
      {tab === "plan" && <DailyPlan sites={sites} />}
      {tab === "realloc" && <ReallocationView sites={sites} />}
      {tab === "weekly" && <WeeklyView />}
      {tourOpen && <Tour onNavigate={setTab} onClose={closeTour} />}
    </div>
  );
}

interface Turn { role: "user" | "assistant"; content: string; tools?: ToolResult[]; }

function AskView() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const examples = [
    "How much should I bake tomorrow (2026-06-29)?",
    "We have a street festival this Saturday — adjust 2026-06-29.",
    "Where am I wasting the most money? Week ending 2026-06-28.",
    "Should I move anything between my shops on 2026-06-29?",
  ];

  async function send(text: string) {
    if (!text.trim() || busy) return;
    const history: ChatTurn[] = turns.map((t) => ({ role: t.role, content: t.content }));
    setTurns((t) => [...t, { role: "user", content: text }]);
    setInput("");
    setBusy(true);
    try {
      const r = await api.chat(text, history);
      setTurns((t) => [...t, { role: "assistant", content: r.reply, tools: r.tool_results }]);
    } catch (e: any) {
      setTurns((t) => [...t, { role: "assistant", content: "Sorry — " + String(e) }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="card">
        <div className="site-title">Ask your operations advisor</div>
        <p className="muted" style={{ fontSize: 13, marginTop: 0 }}>
          Plain-language questions. The agent calls the forecasting & reallocation tools and
          answers with grounded numbers. Mention real-world context (a festival, a heatwave) and
          it adjusts the plan.
        </p>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
          {examples.map((e) => (
            <button key={e} className="ghost" onClick={() => send(e)}>{e}</button>
          ))}
        </div>
        <div className="chat">
          {turns.map((t, i) => (
            <div key={i} className={`bubble ${t.role}`}>
              <div>{t.content}</div>
              {t.tools && t.tools.length > 0 && <ToolData tr={t.tools[0]} />}
            </div>
          ))}
          {busy && <div className="bubble assistant muted">Thinking…</div>}
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
          <input style={{ flex: 1, padding: 10, border: "1px solid var(--line)", borderRadius: 8 }}
            value={input} placeholder="Ask about production, waste, reallocation, margins…"
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send(input)} />
          <button className="primary" onClick={() => send(input)} disabled={busy}>Send</button>
        </div>
      </div>
    </>
  );
}

function ToolData({ tr }: { tr: ToolResult }) {
  const r = tr.result || {};
  if (tr.tool === "get_recommendations" && r.recommendations) {
    const rows = r.recommendations.slice(0, 6);
    return (
      <table style={{ marginTop: 8 }}>
        <thead><tr><th>Product</th><th className="num">Bake</th><th className="num">Leftover €</th></tr></thead>
        <tbody>{rows.map((x: any, i: number) => (
          <tr key={i}><td>{x.product_name} (site {x.site_id})</td>
            <td className="num"><strong>{x.recommended_qty}</strong></td>
            <td className="num eur">{x.predicted_waste_eur ? "€" + x.predicted_waste_eur.toFixed(2) : "—"}</td></tr>
        ))}</tbody>
      </table>
    );
  }
  if (tr.tool === "draft_production_sheet" && r.lines) {
    return <p className="muted" style={{ fontSize: 12 }}>Est. ingredient spend €{r.estimated_ingredient_spend_eur} · {r.lines.length} products</p>;
  }
  return <p className="muted" style={{ fontSize: 11 }}>via tool: {tr.tool}</p>;
}


function DailyPlan({ sites }: { sites: Site[] }) {
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [err, setErr] = useState("");
  useEffect(() => {
    api.recommendations(DAILY_DATE).then(setRecs).catch((e) => setErr(String(e)));
  }, []);
  if (err) return <p className="err">{err}</p>;
  const totalWaste = recs.reduce((s, r) => s + r.predicted_waste_eur, 0);

  return (
    <>
      <div className="card kpis">
        <div className="kpi">
          <div className="label">Production plan for</div>
          <div className="big">{DAILY_DATE}</div>
          <button className="ghost" onClick={() => window.print()}>Print plan</button>
        </div>
        <div className="kpi">
          <div className="label">Predicted leftover if you over-bake</div>
          <div className="big eur">{eur(totalWaste)}</div>
        </div>
      </div>
      {sites.map((site) => {
        const rows = recs.filter((r) => r.site_id === site.id);
        if (!rows.length) return null;
        return (
          <div key={site.id} className="card">
            <div className="site-title">{site.name} <span className="muted">· {site.location}</span></div>
            <table>
              <thead>
                <tr>
                  <th>Product</th><th className="num">Forecast</th><th className="num">Bake</th>
                  <th className="num">Leftover risk</th><th>Confidence</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.product_id}>
                    <td>{r.product_name}<div className="reason">{r.reason}</div></td>
                    <td className="num">{Math.round(r.forecast_qty)}</td>
                    <td className="num"><strong>{r.recommended_qty}</strong></td>
                    <td className="num eur">{r.predicted_waste_eur > 0 ? eur(r.predicted_waste_eur) : "—"}</td>
                    <td><span className={`pill ${r.confidence}`}>{r.confidence}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
      <div className="print-footer">ObradorIQ production sheet — {DAILY_DATE}</div>
    </>
  );
}

export function ReallocationView({ sites }: { sites: Site[] }) {
  const [items, setItems] = useState<Reallocation[]>([]);
  const [err, setErr] = useState("");
  const [decided, setDecided] = useState<Record<number, "accepted" | "dismissed">>({});
  const [busyId, setBusyId] = useState<number | null>(null);
  useEffect(() => {
    api.reallocations(DAILY_DATE).then(setItems).catch((e) => setErr(String(e)));
  }, []);
  if (err) return <p className="err">{err}</p>;
  const total = items.reduce((s, r) => s + r.eur_waste_avoided, 0);

  async function decide(id: number, decision: "accepted" | "dismissed") {
    setBusyId(id);
    try {
      await api.decideReallocation(id, decision);
      setDecided((d) => ({ ...d, [id]: decision }));
    } catch {
      // Leave it undecided so the owner can retry.
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <div className="card kpis">
        <div className="kpi">
          <div className="label">Cross-site reallocations</div>
          <div className="big">{items.length}</div>
        </div>
        <div className="kpi">
          <div className="label">Waste recovered by rebalancing</div>
          <div className="big eur">{eur(total)}</div>
        </div>
      </div>
      {items.length === 0 && <div className="card muted">No reallocation needed — sites are balanced.</div>}
      {items.map((r, i) => {
        const state = r.id != null ? decided[r.id] : undefined;
        return (
          <div key={i} className="card realloc">
            <div className="move">
              Shift {r.quantity} × {r.product_name}: {siteName(sites, r.from_site_id)} → {siteName(sites, r.to_site_id)}
              <span className="eur"> (recovers {eur(r.eur_waste_avoided)})</span>
            </div>
            <p className="reason">{r.justification}</p>
            {state ? (
              <p className={`decision-status ${state}`}>
                {state === "accepted" ? "Approved" : "Dismissed"}
              </p>
            ) : (
              <div>
                <button className="ghost" disabled={r.id == null || busyId === r.id}
                  onClick={() => r.id != null && decide(r.id, "accepted")}>Approve</button>
                <button className="ghost" disabled={r.id == null || busyId === r.id}
                  onClick={() => r.id != null && decide(r.id, "dismissed")}>Dismiss</button>
              </div>
            )}
          </div>
        );
      })}
    </>
  );
}

function WeeklyView() {
  const [w, setW] = useState<Weekly | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { api.weekly(WEEK_END).then(setW).catch((e) => setErr(String(e))); }, []);
  if (err) return <p className="err">{err}</p>;
  if (!w) return <p className="muted">Loading…</p>;
  return (
    <>
      <div className="card kpis">
        <div className="kpi"><div className="label">Week</div><div className="big" style={{ fontSize: 18 }}>{w.week_start} → {w.week_end}</div></div>
        <div className="kpi"><div className="label">Total waste</div><div className="big eur">{eur(w.total_waste_eur)}</div></div>
        <div className="kpi"><div className="label">Recoverable (est.)</div><div className="big eur">{eur(w.eur_avoided_estimate)}</div></div>
      </div>
      <div className="card">
        <div className="site-title">True margin — profit after waste</div>
        <table>
          <thead>
            <tr><th>Product</th><th className="num">Naïve margin</th><th className="num">True margin</th><th className="num">Waste</th></tr>
          </thead>
          <tbody>
            {w.margins.map((m) => (
              <tr key={m.product_id}>
                <td>{m.product_name}</td>
                <td className="num">{m.naive_margin_pct}%</td>
                <td className="num" style={{ color: m.true_margin_pct < m.naive_margin_pct - 5 ? "var(--bad)" : "inherit" }}>
                  {m.true_margin_pct}%
                </td>
                <td className="num eur">{eur(m.waste_eur)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

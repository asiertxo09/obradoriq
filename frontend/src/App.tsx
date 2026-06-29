import { useEffect, useState } from "react";
import {
  api,
  clearToken,
  getToken,
  setToken,
  Reallocation,
  Recommendation,
  Site,
  Weekly,
} from "./api";
import { eur, siteName } from "./format";

const DAILY_DATE = "2026-06-29";
const WEEK_END = "2026-06-28";

export default function App() {
  const [authed, setAuthed] = useState<boolean>(!!getToken());
  if (!authed) return <Login onLogin={() => setAuthed(true)} />;
  return <Dashboard onLogout={() => { clearToken(); setAuthed(false); }} />;
}

function Login({ onLogin }: { onLogin: () => void }) {
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
      </div>
    </div>
  );
}

function Dashboard({ onLogout }: { onLogout: () => void }) {
  const [tab, setTab] = useState<"plan" | "realloc" | "weekly">("plan");
  const [sites, setSites] = useState<Site[]>([]);
  useEffect(() => { api.sites().then(setSites).catch(() => {}); }, []);

  return (
    <div className="app">
      <header className="top">
        <div className="brand">Obrador<span>IQ</span></div>
        <button className="ghost" onClick={onLogout}>Sign out</button>
      </header>
      <p className="tagline">Waste-killer for small bakery chains — every number is profit you keep.</p>
      <div className="tabs">
        <div className={`tab ${tab === "plan" ? "active" : ""}`} onClick={() => setTab("plan")}>Daily plan</div>
        <div className={`tab ${tab === "realloc" ? "active" : ""}`} onClick={() => setTab("realloc")}>Reallocation</div>
        <div className={`tab ${tab === "weekly" ? "active" : ""}`} onClick={() => setTab("weekly")}>Weekly review</div>
      </div>
      {tab === "plan" && <DailyPlan sites={sites} />}
      {tab === "realloc" && <ReallocationView sites={sites} />}
      {tab === "weekly" && <WeeklyView />}
    </div>
  );
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
    </>
  );
}

function ReallocationView({ sites }: { sites: Site[] }) {
  const [items, setItems] = useState<Reallocation[]>([]);
  const [err, setErr] = useState("");
  useEffect(() => {
    api.reallocations(DAILY_DATE).then(setItems).catch((e) => setErr(String(e)));
  }, []);
  if (err) return <p className="err">{err}</p>;
  const total = items.reduce((s, r) => s + r.eur_waste_avoided, 0);
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
      {items.map((r, i) => (
        <div key={i} className="card realloc">
          <div className="move">
            Shift {r.quantity} × {r.product_name}: {siteName(sites, r.from_site_id)} → {siteName(sites, r.to_site_id)}
            <span className="eur"> (recovers {eur(r.eur_waste_avoided)})</span>
          </div>
          <p className="reason">{r.justification}</p>
          <div>
            <button className="ghost">Approve</button>
            <button className="ghost">Dismiss</button>
          </div>
        </div>
      ))}
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

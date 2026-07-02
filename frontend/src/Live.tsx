import { useEffect, useMemo, useRef, useState } from "react";
import { api, IntradayAction, IntradaySignalOut } from "./api";
import { eur } from "./format";

// The intraday "living plan" is anchored to a single demo trading day. The scrubber moves the
// clock across that day; only the time-of-day portion changes as you drag.
const INTRADAY_DATE = "2026-06-28";
const OPEN_MIN = 7 * 60; // 07:00
const CLOSE_MIN = 20 * 60; // 20:00
const STEP_MIN = 15;
const DEFAULT_MIN = 12 * 60; // open the tab at midday

function pad(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}

// minutes-since-midnight -> "HH:MM"
function clock(mins: number): string {
  return `${pad(Math.floor(mins / 60))}:${pad(mins % 60)}`;
}

// minutes-since-midnight -> ISO datetime the backend expects
function asOfIso(mins: number): string {
  return `${INTRADAY_DATE}T${clock(mins)}:00`;
}

// "HH:MM:SS" | "HH:MM" -> "HH:MM"
function shortTime(t: string | null): string {
  if (!t) return "—";
  return t.slice(0, 5);
}

const ACTION_LABEL: Record<IntradayAction, string> = {
  bake_more: "Bake more",
  move: "Move stock",
  markdown: "Mark down",
  hold: "Hold",
};

export default function Live() {
  const [mins, setMins] = useState(DEFAULT_MIN);
  const [signals, setSignals] = useState<IntradaySignalOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [err, setErr] = useState("");
  const firstLoad = useRef(true);

  const asOf = useMemo(() => asOfIso(mins), [mins]);

  // Debounce lightly so scrubbing re-queries without hammering the API, yet still feels live.
  useEffect(() => {
    let cancelled = false;
    if (firstLoad.current) setLoading(true);
    else setUpdating(true);
    const t = setTimeout(() => {
      api
        .getIntraday(asOf)
        .then((rows) => {
          if (cancelled) return;
          setSignals(rows);
          setErr("");
        })
        .catch((e) => {
          if (!cancelled) setErr(String(e));
        })
        .finally(() => {
          if (cancelled) return;
          setLoading(false);
          setUpdating(false);
          firstLoad.current = false;
        });
    }, 180);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [asOf]);

  const actions = signals.filter((s) => s.action !== "hold");
  const totalAtRisk = actions.reduce((s, a) => s + a.eur_at_risk, 0);

  // Group signals by site, preserving first-seen order.
  const bySite = useMemo(() => {
    const order: number[] = [];
    const map = new Map<number, { name: string; rows: IntradaySignalOut[] }>();
    for (const s of signals) {
      if (!map.has(s.site_id)) {
        map.set(s.site_id, { name: s.site_name, rows: [] });
        order.push(s.site_id);
      }
      map.get(s.site_id)!.rows.push(s);
    }
    return order.map((id) => ({ id, ...map.get(id)! }));
  }, [signals]);

  return (
    <>
      <div className="card live-now">
        <div className="live-now-head">
          <div>
            <div className="label muted">Living plan — now</div>
            <div className="big live-clock">{clock(mins)}</div>
            <div className="muted" style={{ fontSize: 12 }}>{INTRADAY_DATE}</div>
          </div>
          <div className="live-atrisk">
            <div className="label muted">€ at risk right now</div>
            <div className="big eur">{eur(totalAtRisk)}</div>
            <div className="muted" style={{ fontSize: 12 }}>
              {actions.length} action{actions.length === 1 ? "" : "s"} recommended
              {updating && <span className="live-updating"> · updating…</span>}
            </div>
          </div>
        </div>
        <div className="live-scrubber">
          <span className="muted" style={{ fontSize: 12 }}>07:00</span>
          <input
            type="range"
            aria-label="Time of day"
            min={OPEN_MIN}
            max={CLOSE_MIN}
            step={STEP_MIN}
            value={mins}
            onChange={(e) => setMins(parseInt(e.target.value, 10))}
          />
          <span className="muted" style={{ fontSize: 12 }}>20:00</span>
        </div>
      </div>

      {err && <p className="err">{err}</p>}
      {loading && !err && <p className="muted">Loading the day…</p>}

      {!loading && !err && (
        <>
          {actions.length > 0 && (
            <div className="live-actions">
              {actions.map((a) => (
                <ActionCard key={`${a.site_id}-${a.product_id}`} s={a} />
              ))}
            </div>
          )}

          {actions.length === 0 && signals.length > 0 && (
            <div className="card live-ontrack">All sites on track for {clock(mins)}.</div>
          )}

          {bySite.map((site) => (
            <div key={site.id} className="card">
              <div className="site-title">{site.name}</div>
              <table>
                <thead>
                  <tr>
                    <th>Product</th>
                    <th className="num">Sold / On hand</th>
                    <th className="num">Projected demand</th>
                    <th className="num">Sellout</th>
                    <th>Action</th>
                    <th>Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {site.rows.map((r) => (
                    <tr key={r.product_id}>
                      <td>{r.product_name}</td>
                      <td className="num">
                        {r.sold_so_far} / <strong>{r.on_hand}</strong>
                      </td>
                      <td className="num">{Math.round(r.projected_demand)}</td>
                      <td className="num">{shortTime(r.projected_sellout_time)}</td>
                      <td>
                        {r.action === "hold" ? (
                          <span className="muted">on track</span>
                        ) : (
                          <span className={`pill action-${r.action}`}>{ACTION_LABEL[r.action]}</span>
                        )}
                      </td>
                      <td>
                        <span className={`pill ${r.confidence}`}>{r.confidence}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}

          {signals.length === 0 && (
            <div className="card muted">No sites reporting for {clock(mins)}.</div>
          )}
        </>
      )}
    </>
  );
}

function ActionCard({ s }: { s: IntradaySignalOut }) {
  const title =
    s.action === "bake_more"
      ? `Bake ${s.action_qty} more ${s.product_name}`
      : s.action === "move"
        ? `Move ${s.action_qty} ${s.product_name}`
        : s.action === "markdown"
          ? `Mark down ${s.action_qty} ${s.product_name}`
          : s.product_name;

  return (
    <div className={`card live-action action-${s.action}`}>
      <div className="live-action-head">
        <span className={`pill action-${s.action}`}>{ACTION_LABEL[s.action]}</span>
        <span className="muted" style={{ fontSize: 12 }}>{s.site_name}</span>
      </div>
      <div className="live-action-title">{title}</div>
      {s.action === "move" && s.from_site_name && (
        <div className="live-action-route">
          {s.from_site_name} <span className="live-arrow">→</span> {s.site_name}
        </div>
      )}
      <p className="reason">{s.reason}</p>
      <div className="live-action-risk">
        <span className="muted" style={{ fontSize: 12 }}>€ at risk</span>
        <span className="big eur">{eur(s.eur_at_risk)}</span>
      </div>
    </div>
  );
}

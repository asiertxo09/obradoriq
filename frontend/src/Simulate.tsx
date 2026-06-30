import { useState } from "react";
import { api, SimulateResult } from "./api";
import { eur } from "./format";

const DEFAULT_SALES = "20,18,22,19,21,17,20,19,22,18,21,20,19,18";

export default function Simulate() {
  const [productName, setProductName] = useState("Croissant");
  const [salesText, setSalesText] = useState(DEFAULT_SALES);
  const [rainyTomorrow, setRainyTomorrow] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SimulateResult | null>(null);
  const [error, setError] = useState("");

  function parseSales(text: string): number[] {
    return text
      .split(",")
      .map((s) => parseInt(s.trim(), 10))
      .filter((n) => !isNaN(n));
  }

  async function submit() {
    const parsed = parseSales(salesText);
    setError("");

    if (parsed.length < 7) {
      setError(`Need at least 7 valid daily sales numbers (you have ${parsed.length})`);
      return;
    }

    setLoading(true);
    try {
      const res = await api.simulate(productName, parsed, rainyTomorrow);
      setResult(res);
    } catch (e: any) {
      setError(String(e) || "API error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <div className="login card">
        <div className="brand">
          Obrador<span>IQ</span>
        </div>
        <h2 style={{ margin: "0 0 4px 0", fontSize: 18, fontWeight: 400, color: "var(--muted)" }}>
          Try it on your bakery
        </h2>

        <div style={{ marginTop: 20 }}>
          <label style={{ display: "block", marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Product name
          </label>
          <input
            value={productName}
            onChange={(e) => setProductName(e.target.value)}
            placeholder="e.g., Croissant"
            style={{ width: "100%", padding: 10, border: "1px solid var(--line)", borderRadius: 8, marginBottom: 12 }}
          />
        </div>

        <div>
          <label style={{ display: "block", marginBottom: 6, fontSize: 13, fontWeight: 500 }}>
            Recent daily sales (14 days, comma-separated)
          </label>
          <textarea
            value={salesText}
            onChange={(e) => setSalesText(e.target.value)}
            rows={3}
            style={{
              width: "100%",
              padding: 10,
              border: "1px solid var(--line)",
              borderRadius: 8,
              fontFamily: "monospace",
              fontSize: 12,
              marginBottom: 12,
            }}
          />
        </div>

        <div style={{ marginBottom: 16 }}>
          <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={rainyTomorrow}
              onChange={(e) => setRainyTomorrow(e.target.checked)}
              style={{ cursor: "pointer" }}
            />
            <span style={{ fontSize: 13 }}>Expecting rain tomorrow</span>
          </label>
        </div>

        <button
          className="primary"
          onClick={submit}
          disabled={loading}
          style={{ width: "100%", marginBottom: 12 }}
        >
          {loading ? "Calculating…" : "Get my recommendation"}
        </button>

        {error && <p className="err">{error}</p>}

        {result && (
          <div className="card" style={{ marginTop: 16, borderLeft: "4px solid var(--accent)" }}>
            <div style={{ marginBottom: 12 }}>
              <div className="big">Bake {result.recommended_qty}</div>
              <div className="muted" style={{ fontSize: 12 }}>{result.product_name}</div>
            </div>
            <div style={{ display: "flex", gap: 16, marginBottom: 12, fontSize: 14 }}>
              <div>
                <div className="muted" style={{ fontSize: 12 }}>Forecast</div>
                <div style={{ fontWeight: 600 }}>{Math.round(result.forecast_qty)}</div>
              </div>
              <div>
                <div className="muted" style={{ fontSize: 12 }}>Leftover risk</div>
                <div className="eur">{eur(result.predicted_waste_eur)}</div>
              </div>
            </div>
            <p className="muted" style={{ fontSize: 13, margin: "8px 0 0 0" }}>
              {result.reason}
            </p>
          </div>
        )}

        <div style={{ marginTop: 20, textAlign: "center" }}>
          <a href="/" style={{ color: "var(--accent)", textDecoration: "none", fontSize: 13 }}>
            → Try the full dashboard (sign in)
          </a>
        </div>
      </div>
    </div>
  );
}

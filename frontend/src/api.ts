// Thin API client. Token kept in localStorage; all calls hit the same-origin /api.
const BASE = "/api";

export function getToken(): string | null {
  return localStorage.getItem("obradoriq_token");
}
export function setToken(t: string) {
  localStorage.setItem("obradoriq_token", t);
}
export function clearToken() {
  localStorage.removeItem("obradoriq_token");
}

async function req(path: string, opts: RequestInit = {}) {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(opts.headers as Record<string, string>),
  };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(BASE + path, { ...opts, headers });
  if (res.status === 401 && token) {
    // Expired/invalid session — drop the token and return to the login screen.
    clearToken();
    window.location.reload();
    throw new Error("Session expired — please sign in again.");
  }
  if (!res.ok) throw new Error((await res.text()) || res.statusText);
  return res.status === 204 ? null : res.json();
}

export const api = {
  login: (email: string, password: string) =>
    req("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  sites: () => req("/sites"),
  recommendations: (date: string) => req(`/recommendations/${date}`),
  reallocations: (date: string) => req(`/recommendations/${date}/reallocation`),
  weekly: (weekEnd: string) => req(`/summary/weekly?week_end=${weekEnd}`),
  decide: (recId: number, decision: string, finalQty?: number) =>
    req(`/recommendations/${recId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, final_qty: finalQty }),
    }),
  chat: (message: string, history: ChatTurn[]) =>
    req("/chat", { method: "POST", body: JSON.stringify({ message, history }) }),
  ingestText: (kind: "sales" | "waste", csv_text: string) =>
    req("/ingest/text", { method: "POST", body: JSON.stringify({ kind, csv_text }) }),
  simulate: (product_name: string, sales_history: number[], rainy_tomorrow: boolean) =>
    req("/simulate", {
      method: "POST",
      body: JSON.stringify({ product_name, sales_history, rainy_tomorrow }),
    }),
};

export interface ChatTurn {
  role: string;
  content: string;
}
export interface ToolResult {
  tool: string;
  args: Record<string, unknown>;
  result: any;
}
export interface ChatReply {
  reply: string;
  tool_results: ToolResult[];
  note?: string;
}

// types
export interface Recommendation {
  id: number | null;
  product_id: number;
  product_name: string;
  site_id: number;
  target_date: string;
  forecast_qty: number;
  recommended_qty: number;
  confidence: string;
  predicted_waste_eur: number;
  reason: string;
}
export interface Reallocation {
  product_name: string;
  from_site_id: number;
  to_site_id: number;
  quantity: number;
  eur_waste_avoided: number;
  justification: string;
}
export interface Site {
  id: number;
  name: string;
  location: string;
}
export interface Margin {
  product_id: number;
  product_name: string;
  naive_margin_pct: number;
  true_margin_pct: number;
  waste_units: number;
  waste_eur: number;
}
export interface Weekly {
  week_start: string;
  week_end: string;
  total_waste_units: number;
  total_waste_eur: number;
  eur_avoided_estimate: number;
  margins: Margin[];
}

export interface SimulateResult {
  product_name: string;
  forecast_qty: number;
  recommended_qty: number;
  predicted_waste_eur: number;
  reason: string;
}

import { useEffect, useMemo, useState } from "react";
import Select from "react-select";
import { api } from "../api";
import PredictionChart from "../components/PredictionChart";

/* --------------------- helpers --------------------- */
const toOptions = (arr) => (arr || []).map((x) => ({ value: x, label: x }));

function normalizeFallbackLevel(level) {
  if (!level) return "";
  const s = String(level).trim().toLowerCase();
  return s.replaceAll(" ", "_").replaceAll("-", "_").replaceAll("+", "_").replaceAll("__", "_");
}

function fallbackMeta(levelRaw) {
  const level = normalizeFallbackLevel(levelRaw);

  const map = {
    exact: { label: "Exact match", tone: "good", desc: "Best quality: exact market series match." },
    latest_in_series: { label: "Used latest history", tone: "mid", desc: "Used closest historical row for this series." },
    state_commodity: {
      label: "State + commodity fallback",
      tone: "warn",
      desc: "Market-level match missing; using wider pattern.",
    },
    commodity_only: {
      label: "Commodity fallback",
      tone: "warn2",
      desc: "Using commodity patterns without market/state precision.",
    },
    date_only: { label: "Date-only", tone: "bad", desc: "Not enough matching history; mostly calendar features." },
  };

  if (level.includes("state") && level.includes("commodity")) return map.state_commodity;
  if (level.includes("commodity") && !level.includes("state")) return map.commodity_only;

  return map[level] || { label: `Fallback: ${levelRaw}`, tone: "neutral", desc: "Unknown fallback type." };
}

function fmtINR(x) {
  if (x === null || x === undefined || Number.isNaN(Number(x))) return "—";
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(Number(x));
}

function downloadJSON(data, filename = "prediction.json") {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function makeSelectStyles(theme) {
  const soft = theme === "soft";
  return {
    control: (base, state) => ({
      ...base,
      backgroundColor: soft ? "rgba(255,255,255,0.92)" : "rgba(30,41,59,0.92)",
      borderColor: state.isFocused
        ? soft
          ? "rgba(16,185,129,0.55)"
          : "rgba(56,189,248,0.75)"
        : soft
        ? "rgba(148,163,184,0.45)"
        : "rgba(71,85,105,0.85)",
      boxShadow: state.isFocused
        ? soft
          ? "0 0 0 3px rgba(16,185,129,0.12)"
          : "0 0 0 2px rgba(56,189,248,0.20)"
        : "none",
      minHeight: "46px",
      borderRadius: 16,
    }),
    singleValue: (base) => ({ ...base, color: soft ? "#0f172a" : "#e2e8f0" }),
    input: (base) => ({ ...base, color: soft ? "#0f172a" : "#e2e8f0" }),
    placeholder: (base) => ({ ...base, color: soft ? "#64748b" : "#94a3b8" }),
    menu: (base) => ({
      ...base,
      backgroundColor: soft ? "rgba(255,255,255,0.98)" : "rgba(15,23,42,0.98)",
      border: soft ? "1px solid rgba(148,163,184,0.35)" : "1px solid rgba(51,65,85,0.8)",
      borderRadius: 16,
      overflow: "hidden",
      zIndex: 9999,
    }),
    option: (base, state) => ({
      ...base,
      backgroundColor: state.isSelected
        ? soft
          ? "rgba(16,185,129,0.14)"
          : "rgba(56,189,248,0.22)"
        : state.isFocused
        ? soft
          ? "rgba(148,163,184,0.16)"
          : "rgba(148,163,184,0.12)"
        : "transparent",
      color: soft ? "#0f172a" : "#e2e8f0",
      cursor: "pointer",
    }),
    indicatorSeparator: () => ({ display: "none" }),
    dropdownIndicator: (base) => ({ ...base, color: soft ? "#475569" : "#94a3b8" }),
    clearIndicator: (base) => ({ ...base, color: soft ? "#475569" : "#94a3b8" }),
  };
}

function Pill({ children, tone = "neutral" }) {
  const cls =
    tone === "good"
      ? "bg-emerald-500/15 border-emerald-500/25 text-emerald-800"
      : tone === "mid"
      ? "bg-amber-500/15 border-amber-500/25 text-amber-800"
      : tone === "warn"
      ? "bg-yellow-500/15 border-yellow-500/25 text-yellow-900"
      : tone === "warn2"
      ? "bg-orange-500/15 border-orange-500/25 text-orange-900"
      : tone === "bad"
      ? "bg-rose-500/15 border-rose-500/25 text-rose-900"
      : "bg-slate-500/10 border-slate-400/25 text-slate-700";
  return <span className={`text-xs border px-3 py-1 rounded-full ${cls}`}>{children}</span>;
}

function Modal({ open, onClose, title, children }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[9999]">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="absolute inset-0 flex items-center justify-center p-4">
        <div className="w-full max-w-3xl rounded-2xl bg-white border border-slate-200 shadow-xl overflow-hidden">
          <div className="px-5 py-4 flex items-center justify-between border-b border-slate-200">
            <div className="font-semibold text-slate-900">{title}</div>
            <button
              onClick={onClose}
              className="text-sm px-3 py-1 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-700"
            >
              Close
            </button>
          </div>
          <div className="p-5">{children}</div>
        </div>
      </div>
    </div>
  );
}

function ConfidenceGauge({ fallbackLevel }) {
  const meta = fallbackMeta(fallbackLevel);
  const level = normalizeFallbackLevel(fallbackLevel);

  const scoreMap = {
    exact: 0.9,
    latest_in_series: 0.7,
    state_commodity: 0.55,
    commodity_only: 0.4,
    date_only: 0.2,
  };

  let score = scoreMap[level];
  if (score === undefined && level.includes("state") && level.includes("commodity")) score = 0.55;
  if (score === undefined) score = 0.5;

  const pct = Math.round(score * 100);

  // --- Clean TOP semicircle gauge (no clipping) ---
  const W = 220;
  const H = 140;
  const cx = 110;
  const cy = 110; // baseline of the semicircle
  const r = 80;
  const stroke = 14;

  const start = Math.PI; // left
  const end = 0;        // right
  const angle = start + (end - start) * score;

  // IMPORTANT: use "-" so the arc goes UP (top semicircle)
  const polar = (a) => ({
    x: cx + r * Math.cos(a),
    y: cy - r * Math.sin(a),
  });

  const arcPath = (a0, a1) => {
    const p0 = polar(a0);
    const p1 = polar(a1);
    return `M ${p0.x} ${p0.y} A ${r} ${r} 0 0 1 ${p1.x} ${p1.y}`;
  };

  const needle = polar(angle);

  return (
    <div className="rounded-3xl border border-slate-200 bg-white/75 backdrop-blur p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-900">Confidence</div>
          <div className="text-xs text-slate-600 mt-1">{meta.desc}</div>
        </div>
        <Pill tone={meta.tone}>{meta.label}</Pill>
      </div>

      <div className="mt-4 flex items-center gap-4">
        <svg width="220" height="120" viewBox={`0 0 ${W} ${H}`} className="shrink-0">
          {/* Track */}
          <path
            style = {{transition: "all 0.6s ease"}}
            d={arcPath(Math.PI, 0)}
            stroke="rgba(148,163,184,0.45)"
            strokeWidth={stroke}
            fill="none"
            strokeLinecap="round"
          />
          {/* Value */}
          <path
            d={arcPath(Math.PI, angle)}
            stroke="rgba(16,185,129,0.9)"
            strokeWidth={stroke}
            fill="none"
            strokeLinecap="round"
          />
          {/* Needle dot */}
          <circle cx={needle.x} cy={needle.y} r="7" fill="rgba(2,132,199,0.95)" />
        </svg>

        <div>
          <div className="text-4xl font-extrabold text-slate-900">{pct}%</div>
          <div className="text-xs text-slate-600 -mt-1">Reliability score</div>
        </div>
      </div>
    </div>
  );
}

/* --------------------- page --------------------- */
export default function Predict() {
  const [theme, setTheme] = useState("soft"); // "soft" | "dark"
  const soft = theme === "soft";
  const selectStyles = useMemo(() => makeSelectStyles(theme), [theme]);

  const [states, setStates] = useState([]);
  const [commodities, setCommodities] = useState([]);
  const [markets, setMarkets] = useState([]);

  const [selectedState, setSelectedState] = useState("");
  const [selectedCommodity, setSelectedCommodity] = useState("");
  const [selectedMarket, setSelectedMarket] = useState("");
  const [arrivalDate, setArrivalDate] = useState("");

  const [result, setResult] = useState(null);
  const [topMarkets, setTopMarkets] = useState([]);
  const [loading, setLoading] = useState(false);

  const [metaLoading, setMetaLoading] = useState(true);
  const [metaError, setMetaError] = useState("");
  const [apiLive, setApiLive] = useState(false);
  const [openDev, setOpenDev] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        await api.get("/health");
        setApiLive(true);
      } catch {
        setApiLive(false);
      }
    })();
  }, []);

  useEffect(() => {
    (async () => {
      setMetaLoading(true);
      setMetaError("");
      try {
        const [s, c] = await Promise.all([api.get("/meta/states"), api.get("/meta/commodities")]);
        const st = s.data.states || [];
        const co = c.data.commodities || [];
        setStates(st);
        setCommodities(co);
        if (st.length === 0 || co.length === 0) setMetaError("Meta loaded but empty. Check train.csv / META_CSV_PATH.");
      } catch {
        setMetaError("Failed to load meta. Check backend + CORS + VITE_API_BASE_URL.");
      } finally {
        setMetaLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    (async () => {
      setMarkets([]);
      setSelectedMarket("");
      setTopMarkets([]);
      setResult(null);
      if (!selectedState) return;

      try {
        const res = await api.get("/meta/markets", { params: { state: selectedState } });
        setMarkets(res.data.markets || []);
      } catch {
        setMarkets([]);
      }
    })();
  }, [selectedState]);

  useEffect(() => {
    (async () => {
      setTopMarkets([]);
      if (!selectedState || !selectedCommodity) return;

      try {
        const res = await api.get("/meta/top-markets", {
          params: { state: selectedState, commodity: selectedCommodity, k: 5 },
        });
        setTopMarkets(res.data.top_markets || []);
      } catch {
        setTopMarkets([]);
      }
    })();
  }, [selectedState, selectedCommodity]);

  const canPredict = useMemo(
    () => selectedState && selectedCommodity && selectedMarket && arrivalDate,
    [selectedState, selectedCommodity, selectedMarket, arrivalDate]
  );

  async function handlePredict() {
    if (!canPredict) return;

    setLoading(true);
    setResult(null);

    const payload = {
      state: selectedState,
      market: selectedMarket,
      commodity: selectedCommodity,
      arrival_date: arrivalDate,
    };

    try {
      const res = await api.post("/predict", payload);
      setResult(res.data);
      setTimeout(
        () => document.getElementById("results")?.scrollIntoView({ behavior: "smooth", block: "start" }),
        50
      );
    } catch {
      alert("Prediction failed. Check backend logs + payload values.");
    } finally {
      setLoading(false);
    }
  }

  function handleReset() {
    setSelectedState("");
    setSelectedCommodity("");
    setSelectedMarket("");
    setArrivalDate("");
    setMarkets([]);
    setTopMarkets([]);
    setResult(null);
  }

  const stateValue = selectedState ? { value: selectedState, label: selectedState } : null;
  const commodityValue = selectedCommodity ? { value: selectedCommodity, label: selectedCommodity } : null;
  const marketValue = selectedMarket ? { value: selectedMarket, label: selectedMarket } : null;

  return (
    <div className={soft ? "min-h-screen bg-transparent text-slate-900" : "min-h-screen bg-slate-950 text-white"}>
      {/* Page Nav (inside Predict only) */}
      <div className="max-w-6xl mx-auto px-4 pt-6 flex items-center justify-end gap-2">
        <Pill tone="neutral">Quantile ML</Pill>
        <Pill tone={apiLive ? "good" : "bad"}>{apiLive ? "API Live" : "API Down"}</Pill>
        <button
          onClick={() => setTheme(soft ? "dark" : "soft")}
          className={
            soft
              ? "text-xs px-3 py-1 rounded-full border border-slate-200 hover:bg-white"
              : "text-xs px-3 py-1 rounded-full border border-slate-700 hover:bg-slate-900/40"
          }
        >
          {soft ? "Soft Mode" : "Dark Mode"}
        </button>
      </div>

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-4 pt-6 pb-8">
        {metaError && (
          <div
            className={
              soft
                ? "mb-6 rounded-2xl p-4 border bg-rose-50 border-rose-200 text-rose-700"
                : "mb-6 rounded-2xl p-4 border bg-rose-500/10 border-rose-400/20 text-rose-200"
            }
          >
            <div className="font-semibold">Meta issue</div>
            <div className="text-sm mt-1">{metaError}</div>
          </div>
        )}

        <div
          className={
            soft
              ? "rounded-[28px] border border-slate-200 bg-white/75 backdrop-blur shadow-sm overflow-hidden"
              : "rounded-[28px] border border-slate-700 bg-slate-900/40 shadow-sm overflow-hidden"
          }
        >
          <div
            className={
              soft
                ? "px-6 py-10 md:px-10 bg-gradient-to-r from-emerald-100/60 via-white to-amber-100/50"
                : "px-6 py-10 md:px-10 bg-gradient-to-r from-sky-500/10 via-slate-900/0 to-emerald-500/10"
            }
          >
            <div className="max-w-3xl">
              <h1
                className={
                  soft
                    ? "text-3xl md:text-5xl font-extrabold tracking-tight text-slate-900"
                    : "text-3xl md:text-5xl font-extrabold tracking-tight text-white"
                }
              >
                Search & Predict Commodity Prices
              </h1>
              <p className={soft ? "mt-3 text-base text-slate-700" : "mt-3 text-base text-slate-300"}>
                Pick a State, Market, Commodity and Date. Get a fair price + a confidence meter.
              </p>
            </div>

            <div className="mt-7 grid grid-cols-1 md:grid-cols-4 gap-3">
              <div>
                <div className={soft ? "text-xs mb-1 text-slate-600" : "text-xs mb-1 text-slate-300"}>State</div>
                <Select
                  styles={selectStyles}
                  options={toOptions(states)}
                  value={stateValue}
                  onChange={(opt) => setSelectedState(opt?.value || "")}
                  placeholder={metaLoading ? "Loading..." : "Search state..."}
                  isClearable
                  isDisabled={metaLoading}
                  noOptionsMessage={() => (metaLoading ? "Loading..." : "No states found")}
                />
              </div>

              <div>
                <div className={soft ? "text-xs mb-1 text-slate-600" : "text-xs mb-1 text-slate-300"}>Market</div>
                <Select
                  styles={selectStyles}
                  options={toOptions(markets)}
                  value={marketValue}
                  onChange={(opt) => setSelectedMarket(opt?.value || "")}
                  placeholder={selectedState ? "Search market..." : "Select state first"}
                  isDisabled={!selectedState || metaLoading}
                  isClearable
                  noOptionsMessage={() => (!selectedState ? "Select state first" : "No markets")}
                />
              </div>

              <div>
                <div className={soft ? "text-xs mb-1 text-slate-600" : "text-xs mb-1 text-slate-300"}>Commodity</div>
                <Select
                  styles={selectStyles}
                  options={toOptions(commodities)}
                  value={commodityValue}
                  onChange={(opt) => setSelectedCommodity(opt?.value || "")}
                  placeholder={metaLoading ? "Loading..." : "Search commodity..."}
                  isClearable
                  isDisabled={metaLoading}
                  noOptionsMessage={() => (metaLoading ? "Loading..." : "No commodities found")}
                />
              </div>

              <div>
                <div className={soft ? "text-xs mb-1 text-slate-600" : "text-xs mb-1 text-slate-300"}>Arrival Date</div>
                <input
                  type="date"
                  className={
                    soft
                      ? "w-full h-[46px] rounded-2xl px-3 border border-slate-200 bg-white/80 text-slate-900"
                      : "w-full h-[46px] rounded-2xl px-3 border border-slate-700 bg-slate-800 text-white"
                  }
                  value={arrivalDate}
                  onChange={(e) => setArrivalDate(e.target.value)}
                />
              </div>
            </div>

            <div className="mt-5 flex flex-wrap items-center gap-2">
              <button
                onClick={handlePredict}
                disabled={!canPredict || loading || metaLoading}
                className={
                  soft
                    ? "px-5 py-2.5 rounded-2xl font-semibold bg-emerald-600 hover:bg-emerald-700 text-white disabled:opacity-50 disabled:cursor-not-allowed"
                    : "px-5 py-2.5 rounded-2xl font-semibold bg-sky-500 hover:bg-sky-400 text-slate-950 disabled:opacity-50 disabled:cursor-not-allowed"
                }
              >
                {loading ? "Predicting…" : "Predict"}
              </button>

              <button
                onClick={handleReset}
                className={
                  soft
                    ? "px-4 py-2.5 rounded-2xl border border-slate-200 hover:bg-white text-sm"
                    : "px-4 py-2.5 rounded-2xl border border-slate-700 hover:bg-slate-900/40 text-sm"
                }
              >
                Reset
              </button>

              {result?.fallback_level && (
                <Pill tone={fallbackMeta(result.fallback_level).tone}>{fallbackMeta(result.fallback_level).label}</Pill>
              )}

              <div className="ml-auto flex gap-2">
                {result && (
                  <>
                    <button
                      onClick={() =>
                        downloadJSON(
                          result,
                          `forecast_${result.state}_${result.market}_${result.commodity}_${result.arrival_date}.json`.replaceAll(
                            " ",
                            "_"
                          )
                        )
                      }
                      className={
                        soft
                          ? "px-4 py-2.5 rounded-2xl border border-slate-200 hover:bg-white text-sm"
                          : "px-4 py-2.5 rounded-2xl border border-slate-700 hover:bg-slate-900/40 text-sm"
                      }
                    >
                      Download JSON
                    </button>
                    <button
                      onClick={() => setOpenDev(true)}
                      className={
                        soft
                          ? "px-4 py-2.5 rounded-2xl border border-slate-200 hover:bg-white text-sm"
                          : "px-4 py-2.5 rounded-2xl border border-slate-700 hover:bg-slate-900/40 text-sm"
                      }
                    >
                      Developer / API
                    </button>
                  </>
                )}
              </div>
            </div>

            {/* How it works strip */}
            <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
              <div className={soft ? "rounded-2xl bg-white/70 border border-slate-200 p-4" : "rounded-2xl bg-slate-950/40 border border-slate-800 p-4"}>
                <div className="font-semibold">1) Input</div>
                <div className={soft ? "text-slate-600 mt-1" : "text-slate-400 mt-1"}>State • Market • Commodity • Date</div>
                </div>
              <div className={soft ? "rounded-2xl bg-white/70 border border-slate-200 p-4" : "rounded-2xl bg-slate-950/40 border border-slate-800 p-4"}>
                <div className="font-semibold">2) Predict</div>
                <div className={soft ? "text-slate-600 mt-1" : "text-slate-400 mt-1"}>Quantile models output a price band</div>
              </div>
              <div className={soft ? "rounded-2xl bg-white/70 border border-slate-200 p-4" : "rounded-2xl bg-slate-950/40 border border-slate-800 p-4"}>
                <div className="font-semibold">3) Decide</div>
                <div className={soft ? "text-slate-600 mt-1" : "text-slate-400 mt-1"}>Confidence meter tells risk</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Results */}
      <section id="results" className="max-w-6xl mx-auto px-4 pb-12">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: primary + chart */}
          <div className="lg:col-span-2 space-y-6">
            <div
              className={
                soft
                  ? "rounded-[28px] border border-slate-200 bg-white/75 backdrop-blur p-6 shadow-sm"
                  : "rounded-[28px] border border-slate-700 bg-slate-900/40 p-6 shadow-sm"
              }
            >
              <div className={soft ? "text-xs text-slate-600" : "text-xs text-slate-400"}>Fair Market Price (prediction)</div>

              <div className="mt-2 flex items-end gap-2">
                <div className={soft ? "text-4xl md:text-6xl font-extrabold tracking-tight text-slate-900" : "text-4xl md:text-6xl font-extrabold tracking-tight text-white"}>
                  <span className={soft ? "text-emerald-700" : "text-sky-300"}>₹</span> {result ? fmtINR(result.q50) : "—"}
                </div>
                <div className={soft ? "pb-2 text-sm text-slate-600" : "pb-2 text-sm text-slate-300"}>per quintal</div>
              </div>

              <div className={soft ? "mt-3 text-sm text-slate-700" : "mt-3 text-sm text-slate-300"}>
                Minimum Expected: <b>₹ {result ? fmtINR(result.q10) : "—"}</b> • Maximum Potential: <b>₹ {result ? fmtINR(result.q90) : "—"}</b>
              </div>

              {!result && !loading && (
                <div className={soft ? "mt-6 rounded-2xl border border-slate-200 bg-white p-5 text-slate-700" : "mt-6 rounded-2xl border border-slate-800 bg-slate-950/40 p-5 text-slate-300"}>
                  Select inputs above and click <b>Predict</b> to generate results.
                </div>
              )}
            </div>

            {result && <PredictionChart q10={result.q10} q50={result.q50} q90={result.q90} theme={theme} />}
          </div>

          {/* Right: confidence + market insights */}
          <div className="space-y-6">
            {result ? (
              <ConfidenceGauge fallbackLevel={result.fallback_level} />
            ) : (
              <div className="rounded-3xl border border-slate-200 bg-white/75 backdrop-blur p-5 shadow-sm">
                <div className="font-semibold text-slate-900">Confidence</div>
                <div className="text-sm text-slate-600 mt-1">Run a prediction to see the meter.</div>
              </div>
            )}

            <div className="rounded-3xl border border-slate-200 bg-white/75 backdrop-blur p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-semibold text-slate-900">Market Insights</div>
                  <div className="text-xs text-slate-600 mt-1">Top markets by historical avg price (demo)</div>
                </div>
                {selectedState && selectedCommodity && <Pill tone="neutral">Top 5</Pill>}
              </div>

              <div className="mt-4 space-y-2">
                {topMarkets.length === 0 ? (
                  <div className="text-sm text-slate-600">
                    Select <b>State + Commodity</b> to see top markets.
                  </div>
                ) : (
                  topMarkets.map((tm, i) => (
                    <div key={i} className="flex justify-between items-center rounded-2xl border border-slate-200 bg-white px-3 py-2 hover:shadow-sm transition">
                      <div className="text-sm text-slate-800">{tm.market}</div>
                      <div className="text-sm font-semibold text-slate-900">₹ {fmtINR(tm.avg_price)}</div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>

        {/* About strip */}
        <div className={soft ? "mt-10 rounded-[28px] border border-slate-200 bg-white/75 p-6" : "mt-10 rounded-[28px] border border-slate-700 bg-slate-900/40 p-6"}>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div>
              <div className="font-semibold">Why this matters</div>
              <p className={soft ? "text-sm text-slate-600 mt-2" : "text-sm text-slate-300 mt-2"}>
                Agri prices fluctuate due to supply, seasonality and market arrivals. This tool predicts a fair price band to support decision making.
              </p>
            </div>
            <div>
              <div className="font-semibold">Model output</div>
              <p className={soft ? "text-sm text-slate-600 mt-2" : "text-sm text-slate-300 mt-2"}>
                We show <b>Minimum Expected</b>, <b>Fair Market Price</b> and <b>Maximum Potential</b> (q10/q50/q90) with uncertainty.
              </p>
            </div>
            <div>
              <div className="font-semibold">Tech</div>
              <p className={soft ? "text-sm text-slate-600 mt-2" : "text-sm text-slate-300 mt-2"}>
                Backend: FastAPI • Models: Quantile ML • Frontend: React + Tailwind + Recharts
              </p>
            </div>
          </div>
        </div>
      </section>

      <Modal open={openDev} onClose={() => setOpenDev(false)} title="Developer / API Response">
        <div className="text-sm text-slate-700 mb-3">Raw JSON for debugging (hidden from normal users).</div>
        <pre className="bg-slate-950 text-slate-100 rounded-xl p-4 text-xs overflow-auto border border-slate-800">
{JSON.stringify(result, null, 2)}
        </pre>
      </Modal>
    </div>
  );
}
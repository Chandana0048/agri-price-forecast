import { useEffect, useMemo, useRef, useState } from "react";
import Select from "react-select";
import { api } from "./api";
import PredictionChart from "./components/PredictionChart";

const toOptions = (arr) => (arr || []).map((x) => ({ value: x, label: x }));

/** Robustly normalize backend fallback strings */
function normalizeFallbackLevel(level) {
  if (!level) return "";
  const s = String(level).trim().toLowerCase();
  return s
    .replaceAll(" ", "_")
    .replaceAll("-", "_")
    .replaceAll("+", "_")
    .replaceAll("__", "_");
}

/** Human-friendly labels (NOW MATCHES BACKEND) */
function fallbackMeta(levelRaw) {
  const level = normalizeFallbackLevel(levelRaw);

  const map = {
    exact: {
      label: "Exact match",
      tone: "good",
      desc: "Best quality: exact market series match.",
    },
    latest_in_series: {
      label: "Used latest history",
      tone: "mid",
      desc: "Used closest historical row for this series.",
    },

    // ✅ support BOTH styles: state_commodity AND state+commodity
    state_commodity: {
      label: "State + commodity fallback",
      tone: "warn",
      desc: "Market-level match missing; using wider pattern.",
    },

    // ✅ IMPORTANT: backend returns 'commodity'
    commodity: {
      label: "Commodity fallback",
      tone: "warn2",
      desc: "Using commodity patterns without market/state precision.",
    },

    // ✅ keep compatibility if you ever return commodity_only
    commodity_only: {
      label: "Commodity fallback",
      tone: "warn2",
      desc: "Using commodity patterns without market/state precision.",
    },

    date_only: {
      label: "Date-only (low confidence)",
      tone: "bad",
      desc: "Not enough matching history; mostly calendar features.",
    },
  };

  // extra robustness
  if (level.includes("state") && level.includes("commodity")) return map.state_commodity;
  if (level === "commodity") return map.commodity;

  return map[level] || {
    label: `Fallback: ${levelRaw}`,
    tone: "neutral",
    desc: "Unknown fallback type.",
  };
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

/** Theme-aware react-select styles */
function makeSelectStyles(theme) {
  const soft = theme === "soft";
  return {
    control: (base, state) => ({
      ...base,
      backgroundColor: soft ? "rgba(255,255,255,0.85)" : "rgba(30, 41, 59, 0.9)",
      borderColor: state.isFocused
        ? (soft ? "rgba(16,185,129,0.55)" : "rgba(56, 189, 248, 0.8)")
        : (soft ? "rgba(148,163,184,0.55)" : "rgba(71, 85, 105, 0.9)"),
      boxShadow: state.isFocused
        ? (soft ? "0 0 0 2px rgba(16,185,129,0.18)" : "0 0 0 1px rgba(56, 189, 248, 0.6)")
        : "none",
      ":hover": {
        borderColor: soft ? "rgba(16,185,129,0.55)" : "rgba(56, 189, 248, 0.6)",
      },
      minHeight: "44px",
      borderRadius: 14,
    }),
    singleValue: (base) => ({ ...base, color: soft ? "#0f172a" : "#e2e8f0" }),
    input: (base) => ({ ...base, color: soft ? "#0f172a" : "#e2e8f0" }),
    placeholder: (base) => ({ ...base, color: soft ? "#64748b" : "#94a3b8" }),
    menu: (base) => ({
      ...base,
      backgroundColor: soft ? "rgba(255,255,255,0.98)" : "rgba(15, 23, 42, 0.98)",
      border: soft ? "1px solid rgba(148,163,184,0.35)" : "1px solid rgba(51, 65, 85, 0.9)",
      zIndex: 9999,
      borderRadius: 14,
      overflow: "hidden",
    }),
    option: (base, state) => ({
      ...base,
      backgroundColor: state.isSelected
        ? (soft ? "rgba(16,185,129,0.18)" : "rgba(56, 189, 248, 0.25)")
        : state.isFocused
        ? (soft ? "rgba(148,163,184,0.18)" : "rgba(148, 163, 184, 0.15)")
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
  // ✅ readable in BOTH soft + dark (no dark: classes dependency)
  const cls =
    tone === "good"
      ? "bg-emerald-100 border-emerald-200 text-emerald-800"
      : tone === "mid"
      ? "bg-amber-100 border-amber-200 text-amber-800"
      : tone === "warn"
      ? "bg-yellow-100 border-yellow-200 text-yellow-900"
      : tone === "warn2"
      ? "bg-orange-100 border-orange-200 text-orange-900"
      : tone === "bad"
      ? "bg-rose-100 border-rose-200 text-rose-800"
      : "bg-slate-100 border-slate-200 text-slate-800";

  return <span className={`text-xs border px-3 py-1 rounded-full ${cls}`}>{children}</span>;
}

/**
 * ✅ FIXED semicircle gauge:
 * Draw TOP arc from π → 2π, not π → 0
 */
function ConfidenceGauge({ fallbackLevel }) {
  const meta = fallbackMeta(fallbackLevel);
  const level = normalizeFallbackLevel(fallbackLevel);

  const scoreMap = {
    exact: 0.9,
    latest_in_series: 0.7,
    state_commodity: 0.55,
    commodity: 0.4,       // ✅ backend value
    commodity_only: 0.4,  // compatibility
    date_only: 0.2,
  };

  let score = scoreMap[level];
  if (score === undefined && level.includes("state") && level.includes("commodity")) score = 0.55;
  if (score === undefined) score = 0.5;

  const pct = Math.round(score * 100);

  const r = 44;
  const cx = 52;
  const cy = 52;

  // top half arc: π to 2π
  const start = Math.PI;
  const end = 2 * Math.PI;
  const angle = start + (end - start) * score;

  const arcPath = (a0, a1) => {
    const x0 = cx + r * Math.cos(a0);
    const y0 = cy + r * Math.sin(a0);
    const x1 = cx + r * Math.cos(a1);
    const y1 = cy + r * Math.sin(a1);
    return `M ${x0} ${y0} A ${r} ${r} 0 0 1 ${x1} ${y1}`;
  };

  const dotX = cx + r * Math.cos(angle);
  const dotY = cy + r * Math.sin(angle);

  return (
    <div className="rounded-2xl border border-slate-200/70 bg-white/70 backdrop-blur p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-900">Confidence Meter</div>
          <div className="text-xs text-slate-600 mt-1">{meta.desc}</div>
        </div>
        <Pill tone={meta.tone}>{meta.label}</Pill>
      </div>

      <div className="mt-4 flex items-center gap-4">
        <svg width="104" height="64" viewBox="0 0 104 64">
          <path
            d={arcPath(Math.PI, 2 * Math.PI)}
            stroke="rgba(148,163,184,0.55)"
            strokeWidth="10"
            fill="none"
            strokeLinecap="round"
          />
          <path
            d={arcPath(Math.PI, angle)}
            stroke="rgba(16,185,129,0.85)"
            strokeWidth="10"
            fill="none"
            strokeLinecap="round"
          />
          <circle cx={dotX} cy={dotY} r="5" fill="rgba(2,132,199,0.95)" />
        </svg>

        <div>
          <div className="text-3xl font-bold text-slate-900">{pct}%</div>
          <div className="text-xs text-slate-600">Model reliability (based on data match quality)</div>
        </div>
      </div>
    </div>
  );
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

export default function App() {
  const [theme, setTheme] = useState("soft"); // "soft" | "dark"
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

  // ✅ Prevent stale responses overwriting new selections
  const reqSeq = useRef(0);

  useEffect(() => {
    async function ping() {
      try {
        await api.get("/health");
        setApiLive(true);
      } catch {
        setApiLive(false);
      }
    }
    ping();
  }, []);

  useEffect(() => {
    async function loadMetaData() {
      setMetaLoading(true);
      setMetaError("");
      try {
        const [s, c] = await Promise.all([api.get("/meta/states"), api.get("/meta/commodities")]);
        const st = s.data.states || [];
        const co = c.data.commodities || [];

        setStates(st);
        setCommodities(co);

        if (st.length === 0 || co.length === 0) {
          setMetaError("Meta loaded but empty. Check train.csv / META_CSV_PATH content.");
        }
      } catch (err) {
        console.error("Meta load failed:", err);
        setMetaError("Failed to load meta. Check backend running + CORS + VITE_API_BASE_URL.");
      } finally {
        setMetaLoading(false);
      }
    }
    loadMetaData();
  }, []);

  useEffect(() => {
    async function loadMarkets() {
      setMarkets([]);
      setSelectedMarket("");
      setTopMarkets([]);
      setResult(null);

      if (!selectedState) return;

      try {
        const res = await api.get("/meta/markets", { params: { state: selectedState } });
        setMarkets(res.data.markets || []);
      } catch (err) {
        console.error("Markets fetch failed:", err);
        setMarkets([]);
      }
    }
    loadMarkets();
  }, [selectedState]);

  useEffect(() => {
    async function loadTopMarkets() {
      setTopMarkets([]);
      if (!selectedState || !selectedCommodity) return;

      try {
        const res = await api.get("/meta/top-markets", {
          params: { state: selectedState, commodity: selectedCommodity, k: 5 },
        });
        setTopMarkets(res.data.top_markets || []);
      } catch (err) {
        console.error("Top markets fetch failed:", err);
        setTopMarkets([]);
      }
    }
    loadTopMarkets();
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

    const myReq = ++reqSeq.current;

    try {
      const res = await api.post("/predict", payload);

      // ✅ only apply latest request response
      if (myReq === reqSeq.current) {
        setResult(res.data);
      }
    } catch (err) {
      console.error("Prediction failed:", err);
      alert("Prediction failed. Check backend logs + payload values.");
    } finally {
      if (myReq === reqSeq.current) setLoading(false);
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

  const derived = useMemo(() => {
    if (!result) return null;
    const q10 = Number(result.q10);
    const q50 = Number(result.q50);
    const q90 = Number(result.q90);
    const spread = Number.isFinite(q90 - q10) ? q90 - q10 : null;

    const bias =
      Number.isFinite(q50) && Number.isFinite(q10) && Number.isFinite(q90)
        ? (q50 - q10) / Math.max(1e-9, q90 - q10)
        : null;

    let mood = { title: "Balanced market", tag: "Neutral", cls: "bg-slate-500/10 border-slate-300/40 text-slate-700" };
    if (bias !== null && bias >= 0.66)
      mood = { title: "Upward pressure", tag: "Bullish", cls: "bg-emerald-500/10 border-emerald-300/50 text-emerald-800" };
    if (bias !== null && bias <= 0.34)
      mood = { title: "Downward pressure", tag: "Bearish", cls: "bg-rose-500/10 border-rose-300/50 text-rose-800" };

    return { spread, bias, mood };
  }, [result]);

  const soft = theme === "soft";

  // ✅ force re-mount so chart/gauge never “stick”
  const resultKey = result
    ? `${result.state}|${result.market}|${result.commodity}|${result.arrival_date}|${result.q50}|${result.fallback_level}`
    : "empty";

  return (
    <div
      className={[
        "min-h-screen",
        soft
          ? "bg-gradient-to-b from-emerald-50 via-white to-amber-50 text-slate-900"
          : "bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-white",
      ].join(" ")}
    >
      <div className={["sticky top-0 z-40 backdrop-blur border-b", soft ? "bg-white/70 border-slate-200" : "bg-slate-950/60 border-slate-800"].join(" ")}>
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={["h-10 w-10 rounded-2xl grid place-items-center border", soft ? "bg-emerald-500/10 border-emerald-300/50" : "bg-sky-500/20 border-sky-400/30"].join(" ")}>
              <span className={["font-bold", soft ? "text-emerald-700" : "text-sky-200"].join(" ")}>₹</span>
            </div>
            <div>
              <div className="font-semibold leading-tight">Agri Price Forecast</div>
              <div className={["text-xs", soft ? "text-slate-600" : "text-slate-400"].join(" ")}>
                Search → Predict → Insight
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Pill tone="neutral">Quantile ML</Pill>
            <Pill tone={apiLive ? "good" : "bad"}>{apiLive ? "API Live" : "API Down"}</Pill>

            <button
              onClick={() => setTheme(soft ? "dark" : "soft")}
              className={["text-xs px-3 py-1 rounded-full border transition", soft ? "border-slate-200 hover:bg-white" : "border-slate-700 bg-slate-900/40 hover:bg-slate-900"].join(" ")}
            >
              {soft ? "Soft Mode" : "Dark Mode"}
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 py-10">
        {metaError && (
          <div className={["mb-6 rounded-2xl p-4 border", soft ? "bg-rose-50 border-rose-200 text-rose-700" : "bg-rose-500/10 border-rose-400/20 text-rose-200"].join(" ")}>
            <div className="font-semibold">Meta issue</div>
            <div className="text-sm mt-1">{metaError}</div>
          </div>
        )}

        <div className={["rounded-3xl border shadow-sm overflow-hidden", soft ? "bg-white/70 border-slate-200" : "bg-slate-900/50 border-slate-700"].join(" ")}>
          <div
            className={[
              "px-6 py-8 md:px-10 md:py-10",
              soft
                ? "bg-gradient-to-r from-emerald-100/60 via-white to-amber-100/50"
                : "bg-gradient-to-r from-sky-500/10 via-slate-900/0 to-emerald-500/10",
            ].join(" ")}
          >
            <div className="max-w-3xl">
              <h1 className={["text-3xl md:text-4xl font-bold tracking-tight", soft ? "text-slate-900" : "text-white"].join(" ")}>
                Predict Market Prices. Understand Risk. Make Better Decisions.
              </h1>
              <p className={["mt-2 text-sm md:text-base", soft ? "text-slate-700" : "text-slate-300"].join(" ")}>
                A clean agri-fintech experience — not a boring admin panel.
              </p>
            </div>

            <div className="mt-6 grid grid-cols-1 md:grid-cols-4 gap-3">
              <div>
                <div className={["text-xs mb-1", soft ? "text-slate-600" : "text-slate-300"].join(" ")}>State</div>
                <Select
                  styles={selectStyles}
                  options={toOptions(states)}
                  value={stateValue}
                  onChange={(opt) => setSelectedState(opt?.value || "")}
                  placeholder={metaLoading ? "Loading..." : "Search state..."}
                  isClearable
                  isDisabled={metaLoading}
                />
              </div>

              <div>
                <div className={["text-xs mb-1", soft ? "text-slate-600" : "text-slate-300"].join(" ")}>Market</div>
                <Select
                  styles={selectStyles}
                  options={toOptions(markets)}
                  value={marketValue}
                  onChange={(opt) => setSelectedMarket(opt?.value || "")}
                  placeholder={selectedState ? "Search market..." : "Select state first"}
                  isDisabled={!selectedState || metaLoading}
                  isClearable
                />
              </div>

              <div>
                <div className={["text-xs mb-1", soft ? "text-slate-600" : "text-slate-300"].join(" ")}>Commodity</div>
                <Select
                  styles={selectStyles}
                  options={toOptions(commodities)}
                  value={commodityValue}
                  onChange={(opt) => setSelectedCommodity(opt?.value || "")}
                  placeholder={metaLoading ? "Loading..." : "Search commodity..."}
                  isClearable
                  isDisabled={metaLoading}
                />
              </div>

              <div>
                <div className={["text-xs mb-1", soft ? "text-slate-600" : "text-slate-300"].join(" ")}>Arrival Date</div>
                <input
                  type="date"
                  className={[
                    "w-full h-[44px] rounded-2xl px-3 border",
                    soft ? "bg-white/80 border-slate-200 text-slate-900" : "bg-slate-800 border-slate-700 text-white",
                  ].join(" ")}
                  value={arrivalDate}
                  onChange={(e) => setArrivalDate(e.target.value)}
                />
              </div>
            </div>

            <div className="mt-5 flex flex-wrap items-center gap-2">
              <button
                onClick={handlePredict}
                disabled={!canPredict || loading || metaLoading}
                className={[
                  "px-5 py-2.5 rounded-2xl font-semibold transition shadow-sm",
                  soft ? "bg-emerald-600 hover:bg-emerald-700 text-white disabled:opacity-50" : "bg-sky-500 hover:bg-sky-400 text-slate-950 disabled:opacity-50",
                  "disabled:cursor-not-allowed",
                ].join(" ")}
              >
                {loading ? "Predicting…" : "Predict"}
              </button>

              <button
                onClick={handleReset}
                className={[
                  "px-4 py-2.5 rounded-2xl border text-sm transition",
                  soft ? "border-slate-200 hover:bg-white" : "border-slate-700 hover:bg-slate-900/40",
                ].join(" ")}
              >
                Reset
              </button>

              {result?.fallback_level && (
                <Pill tone={fallbackMeta(result.fallback_level).tone}>{fallbackMeta(result.fallback_level).label}</Pill>
              )}

              {result && (
                <button
                  onClick={() =>
                    downloadJSON(
                      result,
                      `forecast_${result.state}_${result.market}_${result.commodity}_${result.arrival_date}.json`.replaceAll(" ", "_")
                    )
                  }
                  className={[
                    "ml-auto px-4 py-2.5 rounded-2xl border text-sm transition",
                    soft ? "border-slate-200 hover:bg-white" : "border-slate-700 hover:bg-slate-900/40",
                  ].join(" ")}
                >
                  Download JSON
                </button>
              )}

              {result && (
                <button
                  onClick={() => setOpenDev(true)}
                  className={[
                    "px-4 py-2.5 rounded-2xl border text-sm transition",
                    soft ? "border-slate-200 hover:bg-white" : "border-slate-700 hover:bg-slate-900/40",
                  ].join(" ")}
                >
                  Developer / API
                </button>
              )}
            </div>
          </div>
        </div>

        <div className="mt-8 grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <div className={["rounded-3xl border p-6 shadow-sm", soft ? "bg-white/70 border-slate-200" : "bg-slate-900/60 border-slate-700"].join(" ")}>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className={["text-xs", soft ? "text-slate-600" : "text-slate-400"].join(" ")}>
                    Predicted price (Fair Market Price)
                  </div>
                  <div className="mt-2 flex items-end gap-2">
                    <div className={["text-4xl md:text-5xl font-extrabold tracking-tight", soft ? "text-slate-900" : "text-white"].join(" ")}>
                      <span className={soft ? "text-emerald-700" : "text-sky-300"}>₹</span>{" "}
                      {result ? fmtINR(result.q50) : "—"}
                    </div>
                    <div className={["pb-1 text-sm", soft ? "text-slate-600" : "text-slate-300"].join(" ")}>
                      per quintal
                    </div>
                  </div>
                  <div className={["mt-2 text-sm", soft ? "text-slate-700" : "text-slate-300"].join(" ")}>
                    Minimum Expected: <b>₹ {result ? fmtINR(result.q10) : "—"}</b> • Maximum Potential:{" "}
                    <b>₹ {result ? fmtINR(result.q90) : "—"}</b>
                  </div>
                </div>

                {result && derived?.mood && (
                  <div className={`shrink-0 rounded-2xl border px-4 py-3 ${derived.mood.cls}`}>
                    <div className="text-xs opacity-80">Market Insight</div>
                    <div className="text-lg font-semibold">{derived.mood.tag}</div>
                    <div className="text-xs opacity-80">{derived.mood.title}</div>
                  </div>
                )}
              </div>
            </div>

            {result && (
              <PredictionChart
                key={`chart-${resultKey}`}
                q10={result.q10}
                q50={result.q50}
                q90={result.q90}
                theme={theme}
              />
            )}
          </div>

          <div className="space-y-6">
            {result ? (
              <ConfidenceGauge key={`gauge-${resultKey}`} fallbackLevel={result.fallback_level} />
            ) : (
              <div className="rounded-2xl border border-slate-200/70 bg-white/70 backdrop-blur p-5 shadow-sm">
                <div className="font-semibold text-slate-900">Confidence Meter</div>
                <div className="text-sm text-slate-600 mt-1">Run a prediction to see the confidence gauge.</div>
              </div>
            )}

            <div className="rounded-2xl border border-slate-200/70 bg-white/70 backdrop-blur p-5 shadow-sm">
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
                    <div
                      key={i}
                      className="flex justify-between items-center rounded-xl border border-slate-200 bg-white px-3 py-2 hover:shadow-sm transition"
                    >
                      <div className="text-sm text-slate-800">{tm.market}</div>
                      <div className="text-sm font-semibold text-slate-900">₹ {fmtINR(tm.avg_price)}</div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>

        <footer className="mt-10 text-center text-xs text-slate-500">
          Built with FastAPI + Quantile ML Forecasting + React (Vite)
        </footer>
      </div>

      <Modal open={openDev} onClose={() => setOpenDev(false)} title="Developer / API Response">
        <div className="text-sm text-slate-700 mb-3">
          This is hidden from normal users (good). Use it for debugging / API demo.
        </div>
        <pre className="bg-slate-950 text-slate-100 rounded-xl p-4 text-xs overflow-auto border border-slate-800">
{JSON.stringify(result, null, 2)}
        </pre>
      </Modal>
    </div>
  );
}
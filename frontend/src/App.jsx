import { useEffect, useMemo, useState } from "react";
import Select from "react-select";
import { api } from "./api";
import PredictionChart from "./components/PredictionChart";

const toOptions = (arr) => (arr || []).map((x) => ({ value: x, label: x }));

// Dark theme styles for react-select
const selectStyles = {
  control: (base, state) => ({
    ...base,
    backgroundColor: "rgba(30, 41, 59, 0.9)",
    borderColor: state.isFocused ? "rgba(56, 189, 248, 0.8)" : "rgba(71, 85, 105, 0.9)",
    boxShadow: state.isFocused ? "0 0 0 1px rgba(56, 189, 248, 0.6)" : "none",
    ":hover": { borderColor: "rgba(56, 189, 248, 0.6)" },
    minHeight: "42px",
  }),
  singleValue: (base) => ({ ...base, color: "#e2e8f0" }),
  input: (base) => ({ ...base, color: "#e2e8f0" }),
  placeholder: (base) => ({ ...base, color: "#94a3b8" }),
  menu: (base) => ({
    ...base,
    backgroundColor: "rgba(15, 23, 42, 0.98)",
    border: "1px solid rgba(51, 65, 85, 0.9)",
    zIndex: 9999,
  }),
  option: (base, state) => ({
    ...base,
    backgroundColor: state.isSelected
      ? "rgba(56, 189, 248, 0.25)"
      : state.isFocused
      ? "rgba(148, 163, 184, 0.15)"
      : "transparent",
    color: "#e2e8f0",
    cursor: "pointer",
  }),
  indicatorSeparator: () => ({ display: "none" }),
  dropdownIndicator: (base) => ({ ...base, color: "#94a3b8" }),
  clearIndicator: (base) => ({ ...base, color: "#94a3b8" }),
};

function chip(text) {
  return (
    <span className="text-xs bg-slate-800/70 border border-slate-700 px-3 py-1 rounded-full text-slate-200">
      {text}
    </span>
  );
}

function fallbackBadge(level) {
  if (!level) return null;

  const map = {
    exact: {
      label: "Exact",
      cls: "bg-emerald-500/15 border-emerald-400/30 text-emerald-200",
    },
    latest_in_series: {
      label: "Latest history",
      cls: "bg-amber-500/15 border-amber-400/30 text-amber-200",
    },
    state_commodity: {
      label: "Fallback: state+commodity",
      cls: "bg-yellow-500/15 border-yellow-400/30 text-yellow-200",
    },
    commodity_only: {
      label: "Fallback: commodity",
      cls: "bg-orange-500/15 border-orange-400/30 text-orange-200",
    },
    date_only: {
      label: "Fallback: date-only",
      cls: "bg-rose-500/15 border-rose-400/30 text-rose-200",
    },
  };

  const t =
    map[level] || {
      label: `Fallback: ${level}`,
      cls: "bg-slate-800 border-slate-700 text-slate-200",
    };

  return <span className={`text-xs border px-3 py-1 rounded-full ${t.cls}`}>{t.label}</span>;
}

function fmtINR(x) {
  if (x === null || x === undefined || Number.isNaN(Number(x))) return "—";
  return `₹ ${Number(x).toFixed(2)}`;
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

const HISTORY_KEY = "agri_price_forecast_history_v1";

function loadHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed;
  } catch {
    return [];
  }
}

function saveHistory(items) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(items));
}

function summarizeConfidence(fallbackLevel) {
  // tighter = better
  const map = {
    exact: { label: "High", cls: "text-emerald-200" },
    latest_in_series: { label: "Medium", cls: "text-amber-200" },
    state_commodity: { label: "Medium-Low", cls: "text-yellow-200" },
    commodity_only: { label: "Low", cls: "text-orange-200" },
    date_only: { label: "Very low", cls: "text-rose-200" },
  };
  return map[fallbackLevel] || { label: "Unknown", cls: "text-slate-200" };
}

export default function App() {
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

  const [lastRunAt, setLastRunAt] = useState("");
  const [lastPayload, setLastPayload] = useState(null);

  // ✅ History sidebar
  const [history, setHistory] = useState(() => loadHistory());

  // API health badge
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

  // Load states + commodities
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

  // Markets dependent on state
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

  // Top markets dependent on state + commodity
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

  function handleReset() {
    setSelectedState("");
    setSelectedCommodity("");
    setSelectedMarket("");
    setArrivalDate("");
    setMarkets([]);
    setTopMarkets([]);
    setResult(null);
    setLastRunAt("");
    setLastPayload(null);
  }

  function addToHistory(payload, resData) {
    const entry = {
      id: `${Date.now()}_${Math.random().toString(16).slice(2)}`,
      at: new Date().toLocaleString(),
      payload,
      result: resData,
    };
    const next = [entry, ...history].slice(0, 5);
    setHistory(next);
    saveHistory(next);
  }

  function clearHistory() {
    setHistory([]);
    saveHistory([]);
  }

  function loadFromHistory(entry) {
    const p = entry.payload;
    setSelectedState(p.state || "");
    setSelectedMarket(p.market || "");
    setSelectedCommodity(p.commodity || "");
    setArrivalDate(p.arrival_date || "");
    setResult(entry.result || null);
    setLastPayload(p);
    setLastRunAt(entry.at || "");
  }

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
      setLastPayload(payload);
      setLastRunAt(new Date().toLocaleString());
      addToHistory(payload, res.data);
    } catch (err) {
      console.error("Prediction failed:", err);
      alert("Prediction failed. Check backend logs + payload values.");
    } finally {
      setLoading(false);
    }
  }

  const stateValue = selectedState ? { value: selectedState, label: selectedState } : null;
  const commodityValue = selectedCommodity ? { value: selectedCommodity, label: selectedCommodity } : null;
  const marketValue = selectedMarket ? { value: selectedMarket, label: selectedMarket } : null;

  // ✅ Insights derived from result
  const insights = useMemo(() => {
    if (!result) return null;

    const q10 = Number(result.q10);
    const q50 = Number(result.q50);
    const q90 = Number(result.q90);

    const spread = Number.isFinite(q90 - q10) ? q90 - q10 : null;
    const midBias =
      Number.isFinite(q50) && Number.isFinite(q10) && Number.isFinite(q90)
        ? (q50 - q10) / Math.max(1e-9, q90 - q10)
        : null;

    const conf = summarizeConfidence(result.fallback_level);
    let note = "Model returned a probabilistic range.";
    if (result.fallback_level === "exact") note = "Best quality: exact series match.";
    if (result.fallback_level === "date_only") note = "Low confidence: not enough matching history, mostly date features.";
    if (result.fallback_level === "commodity_only") note = "Lower confidence: using commodity patterns without full market match.";

    return {
      spread,
      midBias,
      conf,
      note,
    };
  }, [result]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-white">
      {/* Top bar */}
      <div className="sticky top-0 z-40 backdrop-blur bg-slate-950/60 border-b border-slate-800">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-sky-500/20 border border-sky-400/30 grid place-items-center">
              <span className="text-sky-200 font-bold">₹</span>
            </div>
            <div>
              <div className="font-semibold leading-tight">Agri Price Forecast</div>
              <div className="text-xs text-slate-400">FastAPI • Quantile ML • React</div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs bg-sky-500/15 border border-sky-400/30 px-3 py-1 rounded-full">
              Quantile ML Model
            </span>

            <span
              className={`text-xs border px-3 py-1 rounded-full ${
                apiLive
                  ? "bg-emerald-500/15 border-emerald-400/30 text-emerald-200"
                  : "bg-rose-500/15 border-rose-400/30 text-rose-200"
              }`}
            >
              {apiLive ? "API Live" : "API Down"}
            </span>

            {result?.fallback_level && fallbackBadge(result.fallback_level)}
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 py-8">
        {/* Banner */}
        {metaError && (
          <div className="mb-6 bg-rose-500/10 border border-rose-400/20 text-rose-200 rounded-2xl p-4">
            <div className="font-semibold">Meta issue</div>
            <div className="text-sm text-rose-100/80 mt-1">{metaError}</div>
            <div className="text-xs text-rose-100/60 mt-2">
              Quick check: open <span className="underline">http://127.0.0.1:8000/meta/states</span>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* LEFT: input */}
          <div className="lg:col-span-1 bg-slate-900/60 border border-slate-700 rounded-2xl p-5 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">Input</h2>
              <div className="flex items-center gap-2">
                {metaLoading && chip("Loading meta…")}
                <button
                  onClick={handleReset}
                  className="text-xs px-3 py-1 rounded-full border border-slate-700 bg-slate-800/60 hover:bg-slate-800 text-slate-200"
                >
                  Reset
                </button>
              </div>
            </div>

            <label className="text-sm text-slate-300">State</label>
            <div className="mt-1 mb-3">
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

            <label className="text-sm text-slate-300">Market</label>
            <div className="mt-1 mb-3">
              <Select
                styles={selectStyles}
                options={toOptions(markets)}
                value={marketValue}
                onChange={(opt) => setSelectedMarket(opt?.value || "")}
                placeholder={selectedState ? "Search market..." : "Select state first"}
                isDisabled={!selectedState || metaLoading}
                isClearable
                noOptionsMessage={() => (!selectedState ? "Select state first" : "No markets for this state")}
              />
            </div>

            <label className="text-sm text-slate-300">Commodity</label>
            <div className="mt-1 mb-3">
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

            <label className="text-sm text-slate-300">Arrival Date</label>
            <input
              type="date"
              className="w-full mt-1 mb-4 bg-slate-800 border border-slate-600 rounded-lg p-2"
              value={arrivalDate}
              onChange={(e) => setArrivalDate(e.target.value)}
            />

            <button
              onClick={handlePredict}
              disabled={!canPredict || loading || metaLoading}
              className="w-full bg-sky-500 hover:bg-sky-400 disabled:opacity-50 disabled:cursor-not-allowed text-slate-950 font-semibold py-2 rounded-xl shadow"
            >
              {loading ? "Predicting..." : "Predict"}
            </button>

            <div className="mt-3 text-xs text-slate-400">
              {lastRunAt ? (
                <span>
                  Last run: <span className="text-slate-200">{lastRunAt}</span>
                </span>
              ) : (
                <span>Tip: pick State → Market → Commodity → Date</span>
              )}
            </div>

            {/* Top Markets */}
            <div className="mt-6">
              <h3 className="text-md font-semibold mb-2">Top Markets</h3>
              <p className="text-xs text-slate-400 mb-2">Based on historical average price (demo insight).</p>

              <div className="space-y-2">
                {topMarkets.length === 0 ? (
                  <div className="text-slate-400 text-sm">
                    {selectedState && selectedCommodity
                      ? "No top markets found for this selection."
                      : "Select State + Commodity to see top markets."}
                  </div>
                ) : (
                  topMarkets.map((tm, i) => (
                    <div
                      key={i}
                      className="flex justify-between bg-slate-800/60 border border-slate-700 rounded-lg px-3 py-2"
                    >
                      <span className="text-slate-200">{tm.market}</span>
                      <span className="text-slate-200 font-medium">₹ {Number(tm.avg_price).toFixed(2)}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* MIDDLE: output */}
          <div className="lg:col-span-2 space-y-6">
            <div className="text-sm text-slate-300">Probabilistic Forecast (q10/q50/q90) • ₹ per quintal</div>

            {(selectedState || selectedMarket || selectedCommodity || arrivalDate) && (
              <div className="flex flex-wrap gap-2">
                {selectedState && chip(selectedState)}
                {selectedMarket && chip(selectedMarket)}
                {selectedCommodity && chip(selectedCommodity)}
                {arrivalDate && chip(arrivalDate)}
              </div>
            )}

            {/* Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <StatCard title="q10 (Low)" value={result?.q10} loading={loading} />
              <StatCard title="q50 (Median)" value={result?.q50} loading={loading} highlight />
              <StatCard title="q90 (High)" value={result?.q90} loading={loading} />
            </div>

            {/* ✅ Insights panel */}
            {result && insights && (
              <div className="bg-slate-900/60 border border-slate-700 rounded-2xl p-5 shadow-xl">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-lg font-semibold">Insights</h3>

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
                    className="text-xs px-3 py-1 rounded-full border border-slate-700 bg-slate-800/60 hover:bg-slate-800 text-slate-200"
                  >
                    Download JSON
                  </button>
                </div>

                <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4">
                    <div className="text-xs text-slate-400">Likely range (q10 → q90)</div>
                    <div className="text-lg font-semibold mt-1">
                      {fmtINR(result.q10)} → {fmtINR(result.q90)}
                    </div>
                    <div className="text-xs text-slate-500 mt-1">wider range = more uncertainty</div>
                  </div>

                  <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4">
                    <div className="text-xs text-slate-400">Spread</div>
                    <div className="text-lg font-semibold mt-1">
                      {insights.spread !== null ? fmtINR(insights.spread) : "—"}
                    </div>
                    <div className="text-xs text-slate-500 mt-1">q90 - q10</div>
                  </div>

                  <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4">
                    <div className="text-xs text-slate-400">Confidence</div>
                    <div className={`text-lg font-semibold mt-1 ${insights.conf.cls}`}>{insights.conf.label}</div>
                    <div className="text-xs text-slate-500 mt-1">{insights.note}</div>
                  </div>
                </div>

                <div className="mt-3 text-xs text-slate-400">
                  Interpretation: q50 is the <span className="text-slate-200">median</span>. q10 and q90 show a
                  probabilistic low/high boundary.
                </div>
              </div>
            )}

            {/* Chart */}
            {result && <PredictionChart q10={result.q10} q50={result.q50} q90={result.q90} />}

            {/* Details */}
            {result && (
              <div className="bg-slate-900/60 border border-slate-700 rounded-2xl p-5 shadow-xl">
                <h3 className="text-lg font-semibold mb-2">Details</h3>

                <div className="flex flex-wrap gap-2 text-xs text-slate-300 mb-3">
                  <span className="bg-slate-800 border border-slate-700 px-3 py-1 rounded-full">
                    {result.state} • {result.market} • {result.commodity}
                  </span>
                  <span className="bg-slate-800 border border-slate-700 px-3 py-1 rounded-full">
                    Date: {result.arrival_date}
                  </span>
                  <span className="bg-slate-800 border border-slate-700 px-3 py-1 rounded-full">
                    Interval width: {Number(result.interval_width).toFixed(2)}
                  </span>
                </div>

                {lastPayload && (
                  <div className="mb-3 text-xs text-slate-400">
                    Request:{" "}
                    <span className="text-slate-200">
                      {lastPayload.state} • {lastPayload.market} • {lastPayload.commodity} • {lastPayload.arrival_date}
                    </span>
                  </div>
                )}

                <pre className="bg-slate-950 border border-slate-800 rounded-xl p-4 text-xs overflow-auto text-slate-200">
{JSON.stringify(result, null, 2)}
                </pre>
              </div>
            )}

            {!result && !loading && (
              <div className="bg-slate-900/40 border border-slate-800 rounded-2xl p-6 text-slate-300">
                <div className="font-semibold mb-1">Ready when you are.</div>
                <div className="text-sm text-slate-400">
                  Select State → Market → Commodity → Date, then click Predict.
                </div>
              </div>
            )}
          </div>

          {/* RIGHT: history sidebar */}
          <div className="lg:col-span-1 bg-slate-900/60 border border-slate-700 rounded-2xl p-5 shadow-xl h-fit">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold">History</h3>
              <button
                onClick={clearHistory}
                className="text-xs px-3 py-1 rounded-full border border-slate-700 bg-slate-800/60 hover:bg-slate-800 text-slate-200"
                disabled={history.length === 0}
              >
                Clear
              </button>
            </div>

            <div className="text-xs text-slate-400 mt-1">Last 5 predictions (saved locally).</div>

            <div className="mt-4 space-y-3">
              {history.length === 0 ? (
                <div className="text-sm text-slate-400">No history yet. Run a prediction.</div>
              ) : (
                history.map((h) => (
                  <button
                    key={h.id}
                    onClick={() => loadFromHistory(h)}
                    className="w-full text-left bg-slate-950/60 border border-slate-800 rounded-xl p-3 hover:bg-slate-950"
                  >
                    <div className="text-xs text-slate-400">{h.at}</div>
                    <div className="text-sm text-slate-200 mt-1 font-semibold">
                      {h.payload?.commodity || "—"}
                    </div>
                    <div className="text-xs text-slate-400 mt-1">
                      {h.payload?.state || "—"} • {h.payload?.market || "—"}
                    </div>
                    <div className="text-xs text-slate-500 mt-2">
                      q50: <span className="text-slate-200">{fmtINR(h.result?.q50)}</span>
                      {h.result?.fallback_level ? (
                        <span className="ml-2">{fallbackBadge(h.result.fallback_level)}</span>
                      ) : null}
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>

        <footer className="mt-10 text-center text-xs text-slate-500">
          Built with FastAPI + Quantile ML Forecasting + React (Vite)
        </footer>
      </div>
    </div>
  );
}

function StatCard({ title, value, highlight = false, loading = false }) {
  const formatted = value !== null && value !== undefined ? `₹ ${Number(value).toFixed(2)} / quintal` : "—";

  return (
    <div
      className={`rounded-2xl p-4 shadow-xl border ${
        highlight ? "bg-sky-500/15 border-sky-400/30" : "bg-slate-900/60 border-slate-700"
      }`}
    >
      <p className="text-xs text-slate-300">{title}</p>

      {loading ? (
        <div className="mt-3 h-8 rounded-lg bg-slate-800/80 animate-pulse" />
      ) : (
        <p className="text-2xl font-bold mt-2">{formatted}</p>
      )}
    </div>
  );
}
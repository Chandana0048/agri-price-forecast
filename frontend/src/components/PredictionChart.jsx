import {
  ResponsiveContainer,
  ComposedChart,
  XAxis,
  YAxis,
  Tooltip,
  Area,
  Line,
  CartesianGrid,
} from "recharts";

function fmtINR(x) {
  if (x === null || x === undefined || Number.isNaN(Number(x))) return "—";
  return `₹ ${Number(x).toFixed(2)}`;
}

/**
 * This chart shows:
 * - a shaded uncertainty band (q10 → q90)
 * - a median line (q50)
 *
 * No extra backend endpoints needed.
 */
export default function PredictionChart({ q10, q50, q90, theme = "soft" }) {
  const low = Number(q10);
  const mid = Number(q50);
  const high = Number(q90);

  const safe = (v) => (Number.isFinite(v) ? v : 0);

  // Build a "range band" using stacked areas:
  // - baseLow is transparent
  // - band = high - low is colored
  const data = [
    { name: "Minimum Expected", baseLow: safe(low), band: Math.max(0, safe(high) - safe(low)), median: safe(mid) },
    { name: "Fair Market Price", baseLow: safe(low), band: Math.max(0, safe(high) - safe(low)), median: safe(mid) },
    { name: "Maximum Potential", baseLow: safe(low), band: Math.max(0, safe(high) - safe(low)), median: safe(mid) },
  ];

  const isSoft = theme === "soft";

  return (
    <div
      className={[
        "rounded-2xl border shadow-sm",
        isSoft
          ? "bg-white/70 border-emerald-200/60 backdrop-blur"
          : "bg-slate-900/60 border-slate-700",
      ].join(" ")}
    >
      <div className="px-5 pt-5 pb-2 flex items-center justify-between">
        <div>
          <h3 className={["text-base font-semibold", isSoft ? "text-slate-900" : "text-white"].join(" ")}>
            Price Range & Uncertainty
          </h3>
          <p className={["text-xs mt-1", isSoft ? "text-slate-600" : "text-slate-400"].join(" ")}>
            Shaded band = expected range (q10→q90) • Line = fair price (q50)
          </p>
        </div>

        <div className={["text-xs", isSoft ? "text-slate-700" : "text-slate-300"].join(" ")}>
          <span className="mr-3">Min: <b>{fmtINR(q10)}</b></span>
          <span className="mr-3">Fair: <b>{fmtINR(q50)}</b></span>
          <span>Max: <b>{fmtINR(q90)}</b></span>
        </div>
      </div>

      <div className="px-3 pb-4">
        <ResponsiveContainer width="100%" height={280}>
          <ComposedChart data={data} margin={{ top: 10, right: 12, bottom: 10, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" opacity={isSoft ? 0.35 : 0.18} />
            <XAxis
              dataKey="name"
              tick={{ fill: isSoft ? "#334155" : "#cbd5e1", fontSize: 12 }}
              axisLine={{ stroke: isSoft ? "#cbd5e1" : "#334155" }}
              tickLine={{ stroke: isSoft ? "#cbd5e1" : "#334155" }}
            />
            <YAxis
              tick={{ fill: isSoft ? "#334155" : "#cbd5e1", fontSize: 12 }}
              axisLine={{ stroke: isSoft ? "#cbd5e1" : "#334155" }}
              tickLine={{ stroke: isSoft ? "#cbd5e1" : "#334155" }}
            />
            <Tooltip
              contentStyle={{
                background: isSoft ? "rgba(255,255,255,0.92)" : "rgba(15,23,42,0.92)",
                border: isSoft ? "1px solid rgba(148,163,184,0.35)" : "1px solid rgba(51,65,85,0.8)",
                borderRadius: 12,
              }}
              formatter={(value, name) => {
                if (name === "median") return [fmtINR(value), "Fair Market Price"];
                if (name === "band") return [fmtINR(value), "Range Width"];
                if (name === "baseLow") return [fmtINR(value), "Minimum Expected"];
                return [value, name];
              }}
            />

            {/* Transparent base */}
            <Area type="monotone" dataKey="baseLow" stackId="1" stroke="none" fill="transparent" />

            {/* Shaded band */}
            <Area
              type="monotone"
              dataKey="band"
              stackId="1"
              stroke="none"
              fill={isSoft ? "rgba(16,185,129,0.25)" : "rgba(56,189,248,0.20)"}
            />

            {/* Median line */}
            <Line
              type="monotone"
              dataKey="median"
              stroke={isSoft ? "rgba(2,132,199,0.95)" : "rgba(56,189,248,0.95)"}
              strokeWidth={3}
              dot={{ r: 4 }}
              activeDot={{ r: 6 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
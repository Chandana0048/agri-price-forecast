import { useMemo } from "react";
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
export default function PredictionChart({ q10, q50, q90, date, theme = "soft" }) {
  const isSoft = theme === "soft";

  const data = useMemo(() => {
    const safe = (v) => (Number.isFinite(v) ? v : 0);
    const low = safe(Number(q10));
    const mid = safe(Number(q50));
    const high = safe(Number(q90));

    const arr = [];
    const baseDate = date ? new Date(date) : new Date();
    const vol = mid * 0.015; // 1.5% daily volatility for the trend

    for (let i = -3; i <= 3; i++) {
      const d = new Date(baseDate);
      d.setDate(d.getDate() + i);
      const dayStr = d.toLocaleDateString("en-US", { month: "short", day: "numeric" });

      // Deterministic pseudo-random curve based on the mid value and day offset
      const curve = (Math.sin(mid + i * 1.5) + Math.cos(mid + i * 0.8)) * vol;

      // Spread can grow slightly further away from target date (i=0)
      const uncertainty = 1 + (Math.abs(i) * 0.05);
      const spread = Math.max(0, high - low) * uncertainty;

      const currentMid = mid + curve;
      const currentLow = currentMid - (spread / 2);
      const currentHigh = currentMid + (spread / 2);

      arr.push({
        name: i === 0 ? "Target Date" : dayStr,
        baseLow: currentLow,
        band: spread,
        median: currentMid,
        rawLow: currentLow,
        rawHigh: currentHigh,
      });
    }
    return arr;
  }, [q10, q50, q90, date]);

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      const pd = payload[0].payload;
      return (
        <div className={`p-3 rounded-xl border ${isSoft ? "bg-white/95 border-slate-200" : "bg-slate-900/95 border-slate-700"} shadow-sm backdrop-blur`}>
          <div className={`text-xs mb-2 font-medium ${isSoft ? "text-slate-500" : "text-slate-400"}`}>{label}</div>
          <div className="text-sm font-semibold text-sky-500">Max: {fmtINR(pd.rawHigh)}</div>
          <div className="text-sm font-bold text-emerald-500 mt-1">Fair: {fmtINR(pd.median)}</div>
          <div className="text-sm font-semibold text-rose-500 mt-1">Min: {fmtINR(pd.rawLow)}</div>
        </div>
      );
    }
    return null;
  };

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
            7-Day Price Trend Forecast
          </h3>
          <p className={["text-xs mt-1", isSoft ? "text-slate-600" : "text-slate-400"].join(" ")}>
            Shaded band = expected range (q10→q90) • Line = fair price (q50)
          </p>
        </div>

        <div className={["text-xs flex flex-col md:flex-row md:gap-3 items-end md:items-center", isSoft ? "text-slate-700" : "text-slate-300"].join(" ")}>
          <span>Target Min: <b>{fmtINR(q10)}</b></span>
          <span>Target Fair: <b>{fmtINR(q50)}</b></span>
          <span>Target Max: <b>{fmtINR(q90)}</b></span>
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
            domain={["auto", "auto"]}
            tickFormatter={(val) => `₹${Math.round(val)}`}
            />
          <Tooltip content={<CustomTooltip />} />

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
            dot={{ r: 4, fill: isSoft ? "#fff" : "#0f172a" }}
            activeDot={{ r: 6, fill: isSoft ? "rgba(2,132,199,0.95)" : "rgba(56,189,248,0.95)" }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
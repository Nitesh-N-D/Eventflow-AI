import { useEffect, useState } from "react";
import { analyticsApi } from "../lib/api";
import type { AnalyticsSummary } from "../types";
import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { CATEGORY_LABELS } from "../lib/utils";
import type { EventCategory } from "../types";

const COLORS = ["#3b82f6", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#06b6d4"];

const TOOLTIP_STYLE = {
  contentStyle: { background: "#0f1623", border: "1px solid #1e2d45", borderRadius: 8, fontSize: 12 },
  labelStyle: { color: "#94a3b8" },
};

export default function AnalyticsPage() {
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null);
  const [accuracy, setAccuracy] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([analyticsApi.summary(), analyticsApi.accuracy()])
      .then(([s, a]) => { setAnalytics(s.data); setAccuracy(a.data); })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
    </div>
  );

  if (!analytics) return <div className="text-muted">Failed to load analytics.</div>;

  const categoryData = Object.entries(analytics.events_by_category).map(([k, v]) => ({
    name: CATEGORY_LABELS[k as EventCategory] ?? k,
    events: v,
  }));

  const delayData = Object.entries(analytics.avg_delay_by_category).map(([k, v]) => ({
    name: CATEGORY_LABELS[k as EventCategory] ?? k,
    "Avg Delay (min)": Math.round(v),
  }));

  const corridorData = analytics.top_affected_corridors.map((c) => ({
    name: c.corridor.length > 20 ? c.corridor.substring(0, 20) + "…" : c.corridor,
    incidents: c.historical_incidents,
  }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Analytics</h1>
        <p className="text-muted text-sm mt-0.5">
          System performance and real historical incident patterns from ASTRAM Bengaluru data
        </p>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Total Events", value: analytics.total_events },
          { label: "Active Now", value: analytics.active_events },
          { label: "High Risk Events", value: analytics.high_risk_events },
          { label: "Avg Congestion Score", value: `${analytics.avg_congestion_score.toFixed(1)}/100` },
        ].map((s) => (
          <div key={s.label} className="stat-card">
            <p className="label">{s.label}</p>
            <p className="text-2xl font-bold mono text-white">{s.value}</p>
          </div>
        ))}
      </div>

      {/* Prediction accuracy card */}
      <div className="glass-card p-5">
        <h3 className="section-title mb-4">Prediction Accuracy (Real Post-Event Feedback)</h3>
        {accuracy?.feedback_count === 0 ? (
          <div className="text-sm text-muted space-y-2">
            <p>No post-event feedback has been submitted yet.</p>
            <p>Once officers mark events as completed and submit actual outcomes,
              real prediction error metrics will appear here.</p>
            <div className="grid grid-cols-2 gap-4 mt-4">
              <div className="bg-surfaceAlt border border-border rounded-lg p-4">
                <p className="text-xs text-muted">Baseline Model R² (Severity)</p>
                <p className="text-2xl font-bold text-good mono">0.851</p>
                <p className="text-xs text-muted mt-1">From real ASTRAM holdout evaluation</p>
              </div>
              <div className="bg-surfaceAlt border border-border rounded-lg p-4">
                <p className="text-xs text-muted">Baseline Model R² (Duration)</p>
                <p className="text-2xl font-bold text-accent mono">0.188</p>
                <p className="text-xs text-muted mt-1">Honest; duration is inherently noisy</p>
              </div>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <div className="stat-card">
              <p className="label">Feedback Count</p>
              <p className="text-2xl font-bold text-white">{accuracy.feedback_count}</p>
            </div>
            <div className="stat-card">
              <p className="label">Avg Duration Error</p>
              <p className="text-2xl font-bold text-amber mono">{accuracy.avg_duration_error_minutes} min</p>
            </div>
            <div className="stat-card">
              <p className="label">Avg Delay Error</p>
              <p className="text-2xl font-bold text-amber mono">{accuracy.avg_delay_error_minutes} min</p>
            </div>
          </div>
        )}
      </div>

      {/* Charts grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Events by category */}
        <div className="glass-card p-5">
          <h3 className="section-title mb-4">Events by Category</h3>
          {categoryData.length === 0 ? (
            <p className="text-muted text-sm">No events yet. Create the first event to see data here.</p>
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={categoryData} dataKey="events" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`} labelLine={false}>
                  {categoryData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip {...TOOLTIP_STYLE} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Avg delay by category */}
        <div className="glass-card p-5">
          <h3 className="section-title mb-4">Average Predicted Delay by Category</h3>
          {delayData.length === 0 ? (
            <p className="text-muted text-sm">No prediction data yet.</p>
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={delayData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#1e2d45" />
                <XAxis type="number" stroke="#64748b" fontSize={11} unit=" min" />
                <YAxis type="category" dataKey="name" stroke="#64748b" fontSize={10} width={120} />
                <Tooltip {...TOOLTIP_STYLE} />
                <Bar dataKey="Avg Delay (min)" fill="#3b82f6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Top risk corridors — real ASTRAM data */}
        <div className="glass-card p-5 lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h3 className="section-title">Top Risk Corridors</h3>
            <span className="text-xs text-muted bg-surfaceAlt border border-border rounded px-2 py-1">
              Real ASTRAM Bengaluru Data · Nov 2023–Apr 2024
            </span>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={corridorData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2d45" />
              <XAxis dataKey="name" stroke="#64748b" fontSize={10} />
              <YAxis stroke="#64748b" fontSize={11} />
              <Tooltip {...TOOLTIP_STYLE} />
              <Bar dataKey="incidents" fill="#f59e0b" radius={[4, 4, 0, 0]}
                name="Historical Incidents" />
            </BarChart>
          </ResponsiveContainer>
          <p className="text-xs text-muted mt-2">
            Historical incident counts from 8,054 real ASTRAM events across 22 Bengaluru corridors.
            Bellary Road 1 is the highest-incident corridor (607 real incidents in the dataset).
          </p>
        </div>
      </div>
    </div>
  );
}

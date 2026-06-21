import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { eventsApi, analyticsApi, corridorsApi } from "../lib/api";
import type { EventOut, AnalyticsSummary, Corridor } from "../types";
import {
  cn, CATEGORY_ICONS, CATEGORY_LABELS,
  congestionColor, formatDateTime,
} from "../lib/utils";
import TrafficMap from "../components/TrafficMap";

function StatCard({ label, value, sub, color }: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div className="stat-card animate-slide-up">
      <p className="text-xs text-muted uppercase tracking-wider">{label}</p>
      <p className={cn("text-3xl font-bold mono", color ?? "text-white")}>{value}</p>
      {sub && <p className="text-xs text-muted">{sub}</p>}
    </div>
  );
}

export default function DashboardPage() {
  const [events, setEvents] = useState<EventOut[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null);
  const [corridors, setCorridors] = useState<Corridor[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      eventsApi.list({ limit: 20 }),
      analyticsApi.summary(),
      corridorsApi.list(),
    ]).then(([ev, an, co]) => {
      setEvents(ev.data);
      setAnalytics(an.data);
      setCorridors(co.data);
    }).finally(() => setLoading(false));

    const interval = setInterval(() => {
      eventsApi.list({ limit: 20 }).then(r => setEvents(r.data));
      analyticsApi.summary().then(r => setAnalytics(r.data));
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  const activeEvents = events.filter(e => e.status === "active");
  const upcomingEvents = events.filter(e => e.status === "upcoming");

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Traffic Command Center</h1>
          <p className="text-muted text-sm mt-0.5">
            Real-time event-driven congestion monitoring · Bengaluru
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="live-dot w-2 h-2 rounded-full bg-good inline-block" />
          <span className="text-xs text-good font-medium">LIVE</span>
          <span className="text-xs text-muted ml-2">{new Date().toLocaleTimeString("en-IN")}</span>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total Events" value={analytics?.total_events ?? 0} sub="all time" />
        <StatCard label="Active Now" value={analytics?.active_events ?? 0}
          color={analytics?.active_events ? "text-amber" : "text-good"} sub="in progress" />
        <StatCard label="High Risk" value={analytics?.high_risk_events ?? 0}
          color={analytics?.high_risk_events ? "text-bad" : "text-good"} sub="congestion ≥ 70" />
        <StatCard label="Avg Congestion"
          value={analytics ? `${analytics.avg_congestion_score.toFixed(0)}/100` : "—"}
          color={congestionColor(analytics?.avg_congestion_score ?? 0)} sub="all predictions" />
      </div>

      {/* Map + active events */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 glass-card p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="section-title">Live Traffic Map</h2>
            <span className="text-xs text-muted">22 real Bengaluru corridors · ASTRAM data</span>
          </div>
          <TrafficMap corridors={corridors} height="360px" />
        </div>

        <div className="glass-card p-4 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h2 className="section-title">Active Events</h2>
            <Link to="/events" className="text-xs text-accent hover:underline">View all</Link>
          </div>
          {activeEvents.length === 0 ? (
            <div className="flex-1 flex items-center justify-center text-muted text-sm">
              No active events right now
            </div>
          ) : (
            <div className="space-y-2 overflow-y-auto max-h-[320px]">
              {activeEvents.map(ev => (
                <Link to={`/events/${ev.id}`} key={ev.id}
                  className="block glass-card-hover p-3 rounded-lg">
                  <div className="flex items-start gap-3">
                    <span className="text-xl">{CATEGORY_ICONS[ev.category]}</span>
                    <div className="min-w-0 flex-1">
                      <p className="font-semibold text-sm truncate">{ev.event_name}</p>
                      <p className="text-xs text-muted">{CATEGORY_LABELS[ev.category]}</p>
                      <p className="text-xs text-muted mt-1">{formatDateTime(ev.start_datetime)}</p>
                    </div>
                    <span className="badge text-amber border-amber/30 bg-amber/10 whitespace-nowrap">
                      ACTIVE
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Top corridors by historical incidents */}
      <div className="glass-card p-4">
        <h2 className="section-title mb-4">Top Risk Corridors — Real ASTRAM Incident History</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {(analytics?.top_affected_corridors ?? []).map((c, i) => {
            const maxCount = analytics?.top_affected_corridors?.[0]?.historical_incidents ?? 1;
            const pct = Math.round((c.historical_incidents / maxCount) * 100);
            return (
              <div key={i} className="bg-surfaceAlt rounded-lg p-3 border border-border">
                <div className="flex justify-between items-start mb-2">
                  <p className="text-sm font-medium">{c.corridor}</p>
                  <span className="mono text-xs text-muted">{c.historical_incidents}</span>
                </div>
                <div className="h-1.5 bg-border rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full bg-accent transition-all duration-700"
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Upcoming events table */}
      {upcomingEvents.length > 0 && (
        <div className="glass-card p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="section-title">Upcoming Events</h2>
            <Link to="/events/new" className="btn-primary text-sm px-3 py-2">+ New Event</Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-muted text-xs uppercase tracking-wider border-b border-border">
                  <th className="text-left pb-3 font-medium">Event</th>
                  <th className="text-left pb-3 font-medium">Category</th>
                  <th className="text-left pb-3 font-medium">Crowd</th>
                  <th className="text-left pb-3 font-medium">Start</th>
                  <th className="text-left pb-3 font-medium">Status</th>
                  <th className="pb-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {upcomingEvents.slice(0, 8).map(ev => (
                  <tr key={ev.id} className="hover:bg-white/2 transition-colors">
                    <td className="py-3 font-medium">{ev.event_name}</td>
                    <td className="py-3 text-muted">
                      {CATEGORY_ICONS[ev.category]} {CATEGORY_LABELS[ev.category]}
                    </td>
                    <td className="py-3 capitalize text-muted">{ev.expected_crowd_size}</td>
                    <td className="py-3 text-muted mono text-xs">{formatDateTime(ev.start_datetime)}</td>
                    <td className="py-3">
                      <span className="badge text-accent border-accent/30 bg-accent/10">UPCOMING</span>
                    </td>
                    <td className="py-3 text-right">
                      <Link to={`/events/${ev.id}`} className="text-accent text-xs hover:underline">
                        View →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

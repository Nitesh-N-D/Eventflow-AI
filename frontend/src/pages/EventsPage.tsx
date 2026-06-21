import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { eventsApi } from "../lib/api";
import type { EventOut, EventStatus } from "../types";
import { CATEGORY_ICONS, CATEGORY_LABELS, formatDateTime, cn } from "../lib/utils";
import { useAuth } from "../hooks/useAuth";

const STATUS_TABS: { label: string; value: EventStatus | "all" }[] = [
  { label: "All", value: "all" },
  { label: "Active", value: "active" },
  { label: "Upcoming", value: "upcoming" },
  { label: "Completed", value: "completed" },
  { label: "Cancelled", value: "cancelled" },
];

const STATUS_COLORS: Record<string, string> = {
  active: "text-amber bg-amber/10 border-amber/30",
  upcoming: "text-accent bg-accent/10 border-accent/30",
  completed: "text-good bg-good/10 border-good/30",
  cancelled: "text-muted bg-white/5 border-border",
};

export default function EventsPage() {
  const { user } = useAuth();
  const [events, setEvents] = useState<EventOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<EventStatus | "all">("all");
  const [search, setSearch] = useState("");

  useEffect(() => {
    setLoading(true);
    eventsApi
      .list({ status_filter: statusFilter === "all" ? undefined : statusFilter, limit: 100 })
      .then((r) => setEvents(r.data))
      .finally(() => setLoading(false));
  }, [statusFilter]);

  const filtered = events.filter((e) =>
    e.event_name.toLowerCase().includes(search.toLowerCase()) ||
    CATEGORY_LABELS[e.category].toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Events</h1>
          <p className="text-muted text-sm mt-0.5">All traffic-impacting events in Bengaluru</p>
        </div>
        {(user?.role === "admin" || user?.role === "traffic_officer") && (
          <Link to="/events/new" className="btn-primary">+ Create Event</Link>
        )}
      </div>

      {/* Search + filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <input
          type="text"
          placeholder="Search events..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="input-field max-w-xs"
        />
        <div className="flex gap-1 flex-wrap">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.value}
              onClick={() => setStatusFilter(tab.value)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-sm font-medium transition-all border",
                statusFilter === tab.value
                  ? "bg-accent text-white border-accent"
                  : "bg-surfaceAlt text-muted border-border hover:text-white"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Events grid */}
      {loading ? (
        <div className="flex items-center justify-center h-40">
          <div className="w-7 h-7 border-2 border-accent border-t-transparent rounded-full animate-spin" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="glass-card p-12 text-center text-muted">
          <p className="text-4xl mb-3">📋</p>
          <p className="font-medium">No events found</p>
          <p className="text-sm mt-1">
            {search ? "Try a different search term" : "Create the first event to get started"}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((ev) => (
            <Link
              key={ev.id}
              to={`/events/${ev.id}`}
              className="glass-card-hover p-4 rounded-xl block animate-slide-up"
            >
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="flex items-start gap-3">
                  <span className="text-2xl">{CATEGORY_ICONS[ev.category]}</span>
                  <div>
                    <p className="font-semibold text-sm leading-tight">{ev.event_name}</p>
                    <p className="text-xs text-muted mt-0.5">{CATEGORY_LABELS[ev.category]}</p>
                  </div>
                </div>
                <span className={cn("badge capitalize whitespace-nowrap", STATUS_COLORS[ev.status])}>
                  {ev.status}
                </span>
              </div>

              <div className="space-y-1.5 text-xs text-muted border-t border-border pt-3">
                <div className="flex justify-between">
                  <span>Crowd</span>
                  <span className="capitalize text-white">{ev.expected_crowd_size}</span>
                </div>
                <div className="flex justify-between">
                  <span>Start</span>
                  <span className="text-white mono">{formatDateTime(ev.start_datetime)}</span>
                </div>
                {ev.weather_condition && (
                  <div className="flex justify-between">
                    <span>Weather</span>
                    <span className="capitalize text-white">{ev.weather_condition}</span>
                  </div>
                )}
              </div>

              <div className="mt-3 text-right">
                <span className="text-xs text-accent">View prediction →</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

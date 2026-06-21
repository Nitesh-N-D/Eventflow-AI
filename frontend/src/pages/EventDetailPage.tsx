import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { eventsApi, feedbackApi, corridorsApi } from "../lib/api";
import type { EventDetail, Corridor } from "../types";
import {
  CATEGORY_ICONS, CATEGORY_LABELS, TRAFFIC_LEVEL_COLORS,
  formatDateTime, formatDuration, cn,
} from "../lib/utils";
import CongestionRing from "../components/CongestionRing";
import TrafficMap from "../components/TrafficMap";
import { useAuth } from "../hooks/useAuth";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="glass-card p-5 space-y-4">
      <h3 className="section-title">{title}</h3>
      {children}
    </div>
  );
}

export default function EventDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const [detail, setDetail] = useState<EventDetail | null>(null);
  const [corridors, setCorridors] = useState<Corridor[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusUpdating, setStatusUpdating] = useState(false);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [fb, setFb] = useState({ actual_duration_minutes: "", actual_delay_minutes: "", actual_officer_count_used: "", notes: "" });
  const [fbLoading, setFbLoading] = useState(false);
  const [fbSuccess, setFbSuccess] = useState(false);
  const [pollingForPrediction, setPollingForPrediction] = useState(false);

  const fetchDetail = () =>
    eventsApi.get(id!).then((r) => setDetail(r.data)).catch(() => {});

  useEffect(() => {
    Promise.all([fetchDetail(), corridorsApi.list().then((r) => setCorridors(r.data))])
      .finally(() => setLoading(false));
  }, [id]);

  // Poll for prediction if not ready yet (background task may still be running)
  useEffect(() => {
    if (!detail) return;
    if (!detail.prediction) {
      setPollingForPrediction(true);
      const poll = setInterval(() => {
        fetchDetail().then(() => {
          if (detail?.prediction) {
            clearInterval(poll);
            setPollingForPrediction(false);
          }
        });
      }, 3000);
      return () => clearInterval(poll);
    } else {
      setPollingForPrediction(false);
    }
  }, [detail?.prediction]);

  const updateStatus = async (status: string) => {
    setStatusUpdating(true);
    await eventsApi.updateStatus(id!, status);
    await fetchDetail();
    setStatusUpdating(false);
  };

  const submitFeedback = async (e: React.FormEvent) => {
    e.preventDefault();
    setFbLoading(true);
    await feedbackApi.submit(id!, {
      actual_duration_minutes: fb.actual_duration_minutes ? Number(fb.actual_duration_minutes) : undefined,
      actual_delay_minutes: fb.actual_delay_minutes ? Number(fb.actual_delay_minutes) : undefined,
      actual_officer_count_used: fb.actual_officer_count_used ? Number(fb.actual_officer_count_used) : undefined,
      notes: fb.notes || undefined,
    });
    setFbSuccess(true);
    setFbLoading(false);
    setFeedbackOpen(false);
    await fetchDetail();
  };

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
    </div>
  );

  if (!detail) return (
    <div className="glass-card p-10 text-center text-muted">Event not found.</div>
  );

  const { event, prediction, resources, diversion_routes, advisory, feedback } = detail;
  const canManage = user?.role === "admin" || user?.role === "traffic_officer";

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-start gap-4">
          <span className="text-4xl">{CATEGORY_ICONS[event.category]}</span>
          <div>
            <h1 className="text-2xl font-bold">{event.event_name}</h1>
            <p className="text-muted text-sm mt-0.5">
              {CATEGORY_LABELS[event.category]} · Created {formatDateTime(event.created_at)}
            </p>
          </div>
        </div>
        {canManage && (
          <div className="flex gap-2 flex-wrap">
            {event.status === "upcoming" && (
              <button onClick={() => updateStatus("active")} disabled={statusUpdating} className="btn-primary text-sm">
                Mark Active
              </button>
            )}
            {event.status === "active" && (
              <button onClick={() => updateStatus("completed")} disabled={statusUpdating} className="btn-primary text-sm">
                Mark Completed
              </button>
            )}
            {event.status === "completed" && !feedback && (
              <button onClick={() => setFeedbackOpen(true)} className="btn-primary text-sm">
                Submit Feedback
              </button>
            )}
          </div>
        )}
      </div>

      {/* Event summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Status", value: event.status.toUpperCase(), color: event.status === "active" ? "text-amber" : event.status === "completed" ? "text-good" : "text-accent" },
          { label: "Crowd Size", value: event.expected_crowd_size.toUpperCase() },
          { label: "Start", value: formatDateTime(event.start_datetime) },
          { label: "Weather", value: event.weather_condition || "Not specified" },
        ].map((item) => (
          <div key={item.label} className="stat-card">
            <p className="text-xs text-muted uppercase tracking-wide">{item.label}</p>
            <p className={cn("font-bold text-sm mono mt-1", item.color ?? "text-white")}>{item.value}</p>
          </div>
        ))}
      </div>

      {/* AI Prediction */}
      {pollingForPrediction && !prediction && (
        <div className="glass-card p-6 flex items-center gap-4">
          <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin shrink-0" />
          <div>
            <p className="font-semibold text-accent">Running AI Prediction...</p>
            <p className="text-sm text-muted mt-0.5">
              Analysing event against real ASTRAM Bengaluru incident patterns
            </p>
          </div>
        </div>
      )}

      {prediction && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Congestion score */}
          <Section title="Traffic Impact Score">
            <div className="flex items-center gap-6">
              <CongestionRing score={Math.round(prediction.congestion_score)} size={100} />
              <div className="space-y-2">
                <div>
                  <p className="text-xs text-muted">Traffic Level</p>
                  <span className={cn("badge mt-1", TRAFFIC_LEVEL_COLORS[prediction.traffic_level])}>
                    {prediction.traffic_level.toUpperCase()}
                  </span>
                </div>
                <div>
                  <p className="text-xs text-muted">Confidence</p>
                  <p className="font-bold text-white">{Math.round(prediction.confidence_score * 100)}%</p>
                </div>
                <div>
                  <p className="text-xs text-muted">Provenance</p>
                  <p className="text-xs text-good">Real ASTRAM Data</p>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-3 border-t border-border pt-3">
              {[
                { label: "Expected Duration", value: formatDuration(prediction.predicted_duration_minutes) },
                { label: "Delay", value: formatDuration(prediction.predicted_delay_minutes) },
                { label: "Affected Radius", value: `${prediction.affected_radius_km.toFixed(1)} km` },
              ].map((s) => (
                <div key={s.label} className="text-center">
                  <p className="text-lg font-bold text-white">{s.value}</p>
                  <p className="text-[10px] text-muted mt-0.5">{s.label}</p>
                </div>
              ))}
            </div>

            {prediction.rare_category_low_confidence && (
              <div className="bg-warn/10 border border-warn/30 rounded-lg px-3 py-2 text-xs text-warn">
                ⚠ Rare event category — limited historical data. Treat prediction as directional.
              </div>
            )}
          </Section>

          {/* AI Explanation */}
          <Section title="AI Explanation">
            <p className="text-sm text-white/80 leading-relaxed">{prediction.explanation}</p>
            <div className="border-t border-border pt-3 space-y-1.5 text-xs text-muted">
              <p>Model R² (severity): <span className="text-white mono">{prediction.model_r2_severity?.toFixed(3) ?? "—"}</span></p>
              <p>Model R² (duration): <span className="text-white mono">{prediction.model_r2_duration?.toFixed(3) ?? "—"}</span></p>
              <p>Data: <span className="text-good">real_historical_astram_event_log</span></p>
            </div>
          </Section>

          {/* Resource requirements */}
          {resources && (
            <Section title="Resource Requirements">
              <div className="grid grid-cols-2 gap-3">
                {[
                  { icon: "👮", label: "Officers", value: resources.recommended_officer_count },
                  { icon: "🚑", label: "Ambulances", value: resources.recommended_ambulance_count },
                  { icon: "📡", label: "Control Rooms", value: resources.recommended_control_room_count },
                  { icon: "🚧", label: "Barricade Points", value: resources.barricade_point_count },
                ].map((r) => (
                  <div key={r.label} className="bg-surfaceAlt border border-border rounded-lg p-3 text-center">
                    <p className="text-2xl mb-1">{r.icon}</p>
                    <p className="text-2xl font-bold text-white">{r.value}</p>
                    <p className="text-[10px] text-muted mt-0.5">{r.label}</p>
                  </div>
                ))}
              </div>
              {resources.barricade_spacing_km && (
                <p className="text-xs text-muted">
                  Barricade spacing: <span className="text-white">{resources.barricade_spacing_km} km</span>
                </p>
              )}
            </Section>
          )}
        </div>
      )}

      {/* Map + Diversion Routes */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <Section title="Traffic Digital Twin — Bengaluru Road Network">
            <TrafficMap
              event={event}
              corridors={corridors}
              diversionRoutes={diversion_routes}
              height="380px"
            />
            <p className="text-xs text-muted">
              Green = low-risk diversion corridors · Red = high-incident corridors (real ASTRAM data)
            </p>
          </Section>
        </div>

        {diversion_routes.length > 0 && (
          <Section title="Recommended Diversion Routes">
            <div className="space-y-3">
              {diversion_routes.map((dr) => (
                <div key={dr.id} className="bg-surfaceAlt border border-border rounded-lg p-3">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-bold text-good">Route {dr.route_rank}</span>
                    <span className="text-xs text-muted">{dr.distance_km.toFixed(1)} km away</span>
                  </div>
                  <p className="font-semibold text-sm">{dr.corridor_name}</p>
                  <div className="flex justify-between mt-2 text-xs text-muted">
                    <span>Est. delay</span>
                    <span className="text-white">{dr.estimated_delay_minutes?.toFixed(0) ?? "—"} min</span>
                  </div>
                </div>
              ))}
            </div>
          </Section>
        )}
      </div>

      {/* Public Advisory */}
      {advisory && (
        <Section title="Public Advisory — Generated Messages">
          <div className="space-y-4">
            {[
              { label: "📱 SMS Format (160 chars)", value: advisory.sms_text, mono: true },
              { label: "🔔 Mobile Notification", value: advisory.notification_text },
              { label: "🖥️ Display Board Format", value: advisory.display_board_text, mono: true },
            ].map((a) => (
              <div key={a.label} className="space-y-1.5">
                <p className="text-xs text-muted font-medium">{a.label}</p>
                <div className="bg-surfaceAlt border border-border rounded-lg px-4 py-3 text-sm text-white/90 leading-relaxed">
                  {a.value}
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Post-event feedback */}
      {feedback && (
        <Section title="Post-Event Feedback (Real Outcomes)">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            {[
              { label: "Actual Duration", value: feedback.actual_duration_minutes ? formatDuration(feedback.actual_duration_minutes) : "—" },
              { label: "Actual Delay", value: feedback.actual_delay_minutes ? formatDuration(feedback.actual_delay_minutes) : "—" },
              { label: "Officers Deployed", value: feedback.actual_officer_count_used ?? "—" },
              { label: "Duration Error", value: feedback.duration_prediction_error_minutes ? `${feedback.duration_prediction_error_minutes.toFixed(0)} min` : "—" },
            ].map((f) => (
              <div key={f.label} className="stat-card">
                <p className="text-xs text-muted">{f.label}</p>
                <p className="font-bold text-white mono">{f.value}</p>
              </div>
            ))}
          </div>
          {feedback.notes && (
            <p className="text-sm text-muted italic border-t border-border pt-3">"{feedback.notes}"</p>
          )}
        </Section>
      )}

      {/* Feedback modal */}
      {feedbackOpen && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4">
          <div className="glass-card p-6 w-full max-w-md animate-slide-up">
            <h3 className="text-lg font-bold mb-4">Submit Post-Event Feedback</h3>
            {fbSuccess && <p className="text-good text-sm mb-3">✓ Feedback submitted!</p>}
            <form onSubmit={submitFeedback} className="space-y-4">
              {[
                { label: "Actual duration (minutes)", field: "actual_duration_minutes" },
                { label: "Actual delay (minutes)", field: "actual_delay_minutes" },
                { label: "Officers actually deployed", field: "actual_officer_count_used" },
              ].map((f) => (
                <div key={f.field}>
                  <label className="label">{f.label}</label>
                  <input
                    type="number" className="input-field"
                    value={fb[f.field as keyof typeof fb]}
                    onChange={(e) => setFb((prev) => ({ ...prev, [f.field]: e.target.value }))}
                  />
                </div>
              ))}
              <div>
                <label className="label">Notes</label>
                <input type="text" className="input-field" value={fb.notes}
                  onChange={(e) => setFb((prev) => ({ ...prev, notes: e.target.value }))}
                  placeholder="Any observations..."
                />
              </div>
              <div className="flex gap-3 pt-2">
                <button type="submit" className="btn-primary flex-1" disabled={fbLoading}>
                  {fbLoading ? "Submitting..." : "Submit Feedback"}
                </button>
                <button type="button" className="btn-ghost flex-1" onClick={() => setFeedbackOpen(false)}>
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

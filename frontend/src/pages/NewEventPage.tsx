import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { eventsApi } from "../lib/api";
import type { EventCategory, CrowdSize } from "../types";
import { CATEGORY_LABELS, CROWD_LABELS } from "../lib/utils";

const CATEGORIES: EventCategory[] = [
  "political_rally", "festival", "sports_event",
  "construction", "accident", "emergency_gathering",
];

const CROWD_SIZES: CrowdSize[] = ["low", "medium", "high", "extreme"];

const WEATHER_OPTIONS = ["clear", "cloudy", "rain", "heavy_rain", "fog"];

const BENGALURU_CORRIDORS = [
  { name: "MG Road / CBD", lat: 12.9757, lon: 77.6011 },
  { name: "Silk Board Junction", lat: 12.9176, lon: 77.6228 },
  { name: "Hebbal Flyover", lat: 13.0358, lon: 77.5970 },
  { name: "Bellary Road (Airport)", lat: 13.0169, lon: 77.5864 },
  { name: "Mysore Road", lat: 12.9558, lon: 77.5343 },
  { name: "Hosur Road (Electronic City)", lat: 12.8391, lon: 77.6767 },
  { name: "Old Madras Road", lat: 12.9950, lon: 77.6680 },
  { name: "Tumkur Road", lat: 13.0358, lon: 77.5200 },
  { name: "Outer Ring Road (East)", lat: 12.9698, lon: 77.7499 },
  { name: "Bannerghatta Road", lat: 12.8727, lon: 77.5970 },
];

export default function NewEventPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  const [form, setForm] = useState({
    event_name: "",
    category: "political_rally" as EventCategory,
    latitude: 12.9716,
    longitude: 77.5946,
    address: "",
    expected_crowd_size: "high" as CrowdSize,
    weather_condition: "clear",
    start_datetime: "",
    end_datetime: "",
    affected_roads: [] as string[],
  });

  const [newRoad, setNewRoad] = useState("");

  const update = (field: string) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setForm((f) => ({ ...f, [field]: e.target.value }));

  const selectLocation = (lat: number, lon: number, addr: string) => {
    setForm((f) => ({ ...f, latitude: lat, longitude: lon, address: addr }));
  };

  const addRoad = () => {
    if (newRoad.trim()) {
      setForm((f) => ({ ...f, affected_roads: [...f.affected_roads, newRoad.trim()] }));
      setNewRoad("");
    }
  };

  const removeRoad = (i: number) =>
    setForm((f) => ({ ...f, affected_roads: f.affected_roads.filter((_, idx) => idx !== i) }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.start_datetime || !form.end_datetime) {
      setError("Start and end datetime are required");
      return;
    }
    if (new Date(form.end_datetime) <= new Date(form.start_datetime)) {
      setError("End time must be after start time");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const payload = {
        ...form,
        start_datetime: new Date(form.start_datetime).toISOString(),
        end_datetime: new Date(form.end_datetime).toISOString(),
      };
      const res = await eventsApi.create(payload);
      setSuccess(true);
      setTimeout(() => navigate(`/events/${res.data.id}`), 1500);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to create event");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Create New Event</h1>
        <p className="text-muted text-sm mt-0.5">
          The AI will automatically predict traffic impact and generate a resource plan
        </p>
      </div>

      {success && (
        <div className="bg-good/10 border border-good/30 text-good rounded-xl px-5 py-4 text-sm font-medium animate-fade-in">
          ✓ Event created! Running AI prediction… redirecting shortly.
        </div>
      )}

      {error && (
        <div className="bg-bad/10 border border-bad/30 text-bad rounded-xl px-5 py-4 text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Event details */}
        <div className="glass-card p-5 space-y-4">
          <h2 className="font-semibold text-white flex items-center gap-2">
            <span className="w-6 h-6 bg-accent/20 rounded text-accent text-xs flex items-center justify-center font-bold">1</span>
            Event Details
          </h2>

          <div>
            <label className="label">Event Name *</label>
            <input
              type="text" value={form.event_name} onChange={update("event_name")}
              className="input-field" placeholder="e.g. Rajyotsava Parade 2024"
              required minLength={3}
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="label">Event Category *</label>
              <select value={form.category} onChange={update("category")} className="input-field">
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>{CATEGORY_LABELS[c]}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Expected Crowd Size *</label>
              <select value={form.expected_crowd_size} onChange={update("expected_crowd_size")} className="input-field">
                {CROWD_SIZES.map((s) => (
                  <option key={s} value={s}>{CROWD_LABELS[s]}</option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="label">Weather Condition</label>
            <select value={form.weather_condition} onChange={update("weather_condition")} className="input-field">
              {WEATHER_OPTIONS.map((w) => (
                <option key={w} value={w}>{w.replace("_", " ").replace(/\b\w/g, l => l.toUpperCase())}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Date & time */}
        <div className="glass-card p-5 space-y-4">
          <h2 className="font-semibold text-white flex items-center gap-2">
            <span className="w-6 h-6 bg-accent/20 rounded text-accent text-xs flex items-center justify-center font-bold">2</span>
            Date &amp; Time
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="label">Start Date &amp; Time *</label>
              <input
                type="datetime-local" value={form.start_datetime}
                onChange={update("start_datetime")} className="input-field" required
              />
            </div>
            <div>
              <label className="label">End Date &amp; Time *</label>
              <input
                type="datetime-local" value={form.end_datetime}
                onChange={update("end_datetime")} className="input-field" required
              />
            </div>
          </div>

          {form.start_datetime && form.end_datetime && (
            <p className="text-xs text-good bg-good/10 border border-good/20 rounded-lg px-3 py-2">
              ✓ Duration:{" "}
              {Math.round(
                (new Date(form.end_datetime).getTime() - new Date(form.start_datetime).getTime()) / 60000
              )}{" "}
              minutes
            </p>
          )}
        </div>

        {/* Location */}
        <div className="glass-card p-5 space-y-4">
          <h2 className="font-semibold text-white flex items-center gap-2">
            <span className="w-6 h-6 bg-accent/20 rounded text-accent text-xs flex items-center justify-center font-bold">3</span>
            Location
          </h2>

          <div>
            <label className="label">Quick-Select Real Bengaluru Corridor</label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {BENGALURU_CORRIDORS.map((c) => (
                <button
                  key={c.name} type="button"
                  onClick={() => selectLocation(c.lat, c.lon, c.name)}
                  className={`text-left px-3 py-2 rounded-lg border text-xs transition-all ${
                    form.address === c.name
                      ? "border-accent bg-accent/15 text-accent"
                      : "border-border bg-surfaceAlt text-muted hover:border-accent/40 hover:text-white"
                  }`}
                >
                  {c.name}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Latitude</label>
              <input
                type="number" step="0.0001" value={form.latitude}
                onChange={(e) => setForm((f) => ({ ...f, latitude: parseFloat(e.target.value) }))}
                className="input-field mono"
              />
            </div>
            <div>
              <label className="label">Longitude</label>
              <input
                type="number" step="0.0001" value={form.longitude}
                onChange={(e) => setForm((f) => ({ ...f, longitude: parseFloat(e.target.value) }))}
                className="input-field mono"
              />
            </div>
          </div>

          <div>
            <label className="label">Address / Venue Description</label>
            <input
              type="text" value={form.address} onChange={update("address")}
              className="input-field" placeholder="e.g. Kanteerava Stadium, Kasturba Road"
            />
          </div>
        </div>

        {/* Affected roads */}
        <div className="glass-card p-5 space-y-4">
          <h2 className="font-semibold text-white flex items-center gap-2">
            <span className="w-6 h-6 bg-accent/20 rounded text-accent text-xs flex items-center justify-center font-bold">4</span>
            Affected Roads (optional)
          </h2>

          <div className="flex gap-2">
            <input
              type="text" value={newRoad}
              onChange={(e) => setNewRoad(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addRoad())}
              className="input-field flex-1" placeholder="e.g. MG Road, Brigade Road"
            />
            <button type="button" onClick={addRoad} className="btn-primary px-4">Add</button>
          </div>

          {form.affected_roads.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {form.affected_roads.map((road, i) => (
                <span key={i} className="flex items-center gap-1.5 bg-accent/10 border border-accent/25 text-accent text-xs px-3 py-1.5 rounded-full">
                  {road}
                  <button type="button" onClick={() => removeRoad(i)} className="hover:text-white ml-1">×</button>
                </span>
              ))}
            </div>
          )}
        </div>

        {/* AI prediction notice */}
        <div className="bg-accent/5 border border-accent/20 rounded-xl p-4 text-sm text-muted">
          <p className="text-accent font-semibold mb-1">🤖 AI Prediction will run automatically</p>
          After creating the event, the system will use the real ASTRAM-trained ML ensemble
          to predict traffic impact, generate resource requirements, recommend diversion routes,
          and produce public advisories — all within seconds.
        </div>

        <button type="submit" className="btn-primary w-full py-3 text-base" disabled={loading || success}>
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <span className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Creating event &amp; running AI analysis...
            </span>
          ) : "Create Event &amp; Generate AI Prediction"}
        </button>
      </form>
    </div>
  );
}

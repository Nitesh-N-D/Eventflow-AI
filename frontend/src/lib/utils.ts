import type { TrafficLevel, EventCategory, CrowdSize } from "../types";

export function cn(...classes: (string | false | undefined | null)[]) {
  return classes.filter(Boolean).join(" ");
}

export const CATEGORY_LABELS: Record<EventCategory, string> = {
  political_rally: "Political Rally",
  festival: "Festival",
  sports_event: "Sports Event",
  construction: "Construction",
  accident: "Accident",
  emergency_gathering: "Emergency Gathering",
};

export const CATEGORY_ICONS: Record<EventCategory, string> = {
  political_rally: "🗳️",
  festival: "🎉",
  sports_event: "🏟️",
  construction: "🚧",
  accident: "🚨",
  emergency_gathering: "⚠️",
};

export const CROWD_LABELS: Record<CrowdSize, string> = {
  low: "Low (<5,000)",
  medium: "Medium (5K–20K)",
  high: "High (20K–70K)",
  extreme: "Extreme (>70K)",
};

export const TRAFFIC_LEVEL_COLORS: Record<TrafficLevel, string> = {
  low: "text-good bg-good/10 border-good/30",
  medium: "text-amber bg-amber/10 border-amber/30",
  high: "text-bad bg-bad/10 border-bad/30",
  critical: "text-critical bg-critical/10 border-critical/30",
};

export const TRAFFIC_LEVEL_DOT: Record<TrafficLevel, string> = {
  low: "bg-good",
  medium: "bg-amber",
  high: "bg-bad",
  critical: "bg-critical",
};

export function congestionColor(score: number): string {
  if (score >= 80) return "text-critical";
  if (score >= 60) return "text-bad";
  if (score >= 35) return "text-amber";
  return "text-good";
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit", hour12: true,
  });
}

export function formatDuration(minutes: number): string {
  if (minutes < 60) return `${Math.round(minutes)} min`;
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes % 60);
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

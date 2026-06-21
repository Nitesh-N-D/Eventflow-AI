// ─── Auth ─────────────────────────────────────────────────────────────────
export type UserRole = "admin" | "traffic_officer" | "public_user";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  role: UserRole;
  full_name: string;
}

// ─── Events ───────────────────────────────────────────────────────────────
export type EventCategory =
  | "political_rally"
  | "festival"
  | "sports_event"
  | "construction"
  | "accident"
  | "emergency_gathering";

export type CrowdSize = "low" | "medium" | "high" | "extreme";
export type EventStatus = "upcoming" | "active" | "completed" | "cancelled";
export type TrafficLevel = "low" | "medium" | "high" | "critical";

export interface EventCreate {
  event_name: string;
  category: EventCategory;
  latitude: number;
  longitude: number;
  address?: string;
  expected_crowd_size: CrowdSize;
  weather_condition?: string;
  start_datetime: string;
  end_datetime: string;
  affected_roads?: string[];
}

export interface EventOut {
  id: string;
  event_name: string;
  category: EventCategory;
  expected_crowd_size: CrowdSize;
  weather_condition?: string;
  start_datetime: string;
  end_datetime: string;
  affected_roads?: string[];
  status: EventStatus;
  created_at: string;
  location?: {
    id: string;
    address?: string;
    nearest_corridor_id?: string;
    distance_to_corridor_km?: number;
  };
}

// ─── Predictions ──────────────────────────────────────────────────────────
export interface Prediction {
  id: string;
  event_id: string;
  congestion_score: number;
  traffic_level: TrafficLevel;
  predicted_duration_minutes: number;
  predicted_delay_minutes: number;
  affected_radius_km: number;
  severity_score: number;
  confidence_score: number;
  model_r2_duration?: number;
  model_r2_severity?: number;
  rare_category_low_confidence: boolean;
  explanation: string;
  input_features_used: Record<string, unknown>;
  data_provenance: string;
  created_at: string;
}

// ─── Resources ────────────────────────────────────────────────────────────
export interface Resource {
  id: string;
  event_id: string;
  recommended_officer_count: number;
  recommended_ambulance_count: number;
  recommended_control_room_count: number;
  barricade_point_count: number;
  barricade_spacing_km?: number;
  estimated_footprint_km?: number;
  historical_road_closure_rate?: number;
  rationale: string;
  actual_officer_count_deployed?: number;
}

// ─── Diversion ────────────────────────────────────────────────────────────
export interface DiversionRoute {
  id: string;
  alternate_corridor_id: string;
  corridor_name: string;
  distance_km: number;
  historical_total_incidents: number;
  estimated_delay_minutes?: number;
  route_rank: number;
}

// ─── Advisory ─────────────────────────────────────────────────────────────
export interface Advisory {
  id: string;
  event_id: string;
  sms_text: string;
  notification_text: string;
  display_board_text: string;
  created_at: string;
}

// ─── Feedback ─────────────────────────────────────────────────────────────
export interface Feedback {
  id: string;
  event_id: string;
  prediction_id: string;
  actual_duration_minutes?: number;
  actual_delay_minutes?: number;
  actual_officer_count_used?: number;
  actual_congestion_score?: number;
  duration_prediction_error_minutes?: number;
  delay_prediction_error_minutes?: number;
  notes?: string;
  created_at: string;
}

// ─── Event Detail (combined) ───────────────────────────────────────────────
export interface EventDetail {
  event: EventOut;
  prediction?: Prediction;
  resources?: Resource;
  diversion_routes: DiversionRoute[];
  advisory?: Advisory;
  feedback?: Feedback;
}

// ─── Analytics ────────────────────────────────────────────────────────────
export interface AnalyticsSummary {
  total_events: number;
  active_events: number;
  high_risk_events: number;
  avg_congestion_score: number;
  avg_prediction_accuracy_pct?: number;
  events_by_category: Record<string, number>;
  top_affected_corridors: Array<{ corridor: string; historical_incidents: number }>;
  avg_delay_by_category: Record<string, number>;
}

// ─── Corridors ────────────────────────────────────────────────────────────
export interface Corridor {
  id: string;
  corridor_name: string;
  latitude: number;
  longitude: number;
  historical_incident_count: number;
  zone?: string;
}

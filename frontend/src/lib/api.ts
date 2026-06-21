import axios from "axios";
import type {
  TokenResponse, User, EventCreate, EventOut, EventDetail,
  AnalyticsSummary, Corridor, Feedback,
} from "../types";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
});

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// On 401, clear token and redirect to login
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

// ─── Auth ──────────────────────────────────────────────────────────────────
export const authApi = {
  register: (data: { email: string; password: string; full_name: string; role: string }) =>
    api.post<User>("/auth/register", data),
  login: (email: string, password: string) =>
    api.post<TokenResponse>("/auth/login", { email, password }),
  me: () => api.get<User>("/auth/me"),
};

// ─── Events ───────────────────────────────────────────────────────────────
export const eventsApi = {
  create: (data: EventCreate) => api.post<EventOut>("/events/", data),
  list: (params?: { status_filter?: string; limit?: number; offset?: number }) =>
    api.get<EventOut[]>("/events/", { params }),
  get: (id: string) => api.get<EventDetail>(`/events/${id}`),
  updateStatus: (id: string, status: string) =>
    api.patch(`/events/${id}/status`, null, { params: { new_status: status } }),
};

// ─── Feedback ─────────────────────────────────────────────────────────────
export const feedbackApi = {
  submit: (eventId: string, data: Partial<Feedback>) =>
    api.post<Feedback>(`/feedback/${eventId}`, data),
};

// ─── Analytics ────────────────────────────────────────────────────────────
export const analyticsApi = {
  summary: () => api.get<AnalyticsSummary>("/analytics/summary"),
  accuracy: () => api.get("/analytics/prediction-accuracy"),
};

// ─── Corridors ────────────────────────────────────────────────────────────
export const corridorsApi = {
  list: () => api.get<Corridor[]>("/corridors/"),
};

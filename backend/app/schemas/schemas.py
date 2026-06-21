from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator
import re


# ─── Auth ────────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2)
    role: str = Field(default="public_user")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        allowed = {"admin", "traffic_officer", "public_user"}
        if v not in allowed:
            raise ValueError(f"role must be one of {allowed}")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str
    full_name: str


class UserOut(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Events ──────────────────────────────────────────────────────────────────

class LocationCreate(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    address: Optional[str] = None


class EventCreate(BaseModel):
    event_name: str = Field(min_length=3, max_length=255)
    category: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    address: Optional[str] = None
    expected_crowd_size: str
    weather_condition: Optional[str] = None
    start_datetime: datetime
    end_datetime: datetime
    affected_roads: Optional[List[str]] = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        allowed = {"political_rally", "festival", "sports_event", "construction", "accident", "emergency_gathering"}
        if v not in allowed:
            raise ValueError(f"category must be one of {allowed}")
        return v

    @field_validator("expected_crowd_size")
    @classmethod
    def validate_crowd(cls, v):
        allowed = {"low", "medium", "high", "extreme"}
        if v not in allowed:
            raise ValueError(f"expected_crowd_size must be one of {allowed}")
        return v


class EventOut(BaseModel):
    id: UUID
    event_name: str
    category: str
    expected_crowd_size: str
    weather_condition: Optional[str]
    start_datetime: datetime
    end_datetime: datetime
    affected_roads: Optional[List[str]]
    status: str
    created_at: datetime
    location: Optional[LocationOut] = None

    model_config = {"from_attributes": True}


class LocationOut(BaseModel):
    id: UUID
    address: Optional[str]
    nearest_corridor_id: Optional[UUID]
    distance_to_corridor_km: Optional[float]

    model_config = {"from_attributes": True}


EventOut.model_rebuild()


# ─── Predictions ─────────────────────────────────────────────────────────────

class PredictionOut(BaseModel):
    id: UUID
    event_id: UUID
    congestion_score: float
    traffic_level: str
    predicted_duration_minutes: float
    predicted_delay_minutes: float
    affected_radius_km: float
    severity_score: float
    confidence_score: float
    model_r2_duration: Optional[float]
    model_r2_severity: Optional[float]
    rare_category_low_confidence: bool
    explanation: str
    input_features_used: dict
    data_provenance: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Resources ───────────────────────────────────────────────────────────────

class ResourceOut(BaseModel):
    id: UUID
    event_id: UUID
    recommended_officer_count: int
    recommended_ambulance_count: int
    recommended_control_room_count: int
    barricade_point_count: int
    barricade_spacing_km: Optional[float]
    estimated_footprint_km: Optional[float]
    historical_road_closure_rate: Optional[float]
    rationale: str
    actual_officer_count_deployed: Optional[int]

    model_config = {"from_attributes": True}


# ─── Diversions ──────────────────────────────────────────────────────────────

class DiversionRouteOut(BaseModel):
    id: UUID
    alternate_corridor_id: UUID
    corridor_name: str
    distance_km: float
    historical_total_incidents: int
    estimated_delay_minutes: Optional[float]
    route_rank: int

    model_config = {"from_attributes": True}


# ─── Advisory ────────────────────────────────────────────────────────────────

class AdvisoryOut(BaseModel):
    id: UUID
    event_id: UUID
    sms_text: str
    notification_text: str
    display_board_text: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Feedback ────────────────────────────────────────────────────────────────

class FeedbackCreate(BaseModel):
    actual_duration_minutes: Optional[float] = None
    actual_delay_minutes: Optional[float] = None
    actual_officer_count_used: Optional[int] = None
    actual_congestion_score: Optional[float] = None
    notes: Optional[str] = None


class FeedbackOut(BaseModel):
    id: UUID
    event_id: UUID
    prediction_id: UUID
    actual_duration_minutes: Optional[float]
    actual_delay_minutes: Optional[float]
    actual_officer_count_used: Optional[int]
    actual_congestion_score: Optional[float]
    duration_prediction_error_minutes: Optional[float]
    delay_prediction_error_minutes: Optional[float]
    notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Analytics ───────────────────────────────────────────────────────────────

class AnalyticsSummary(BaseModel):
    total_events: int
    active_events: int
    high_risk_events: int
    avg_congestion_score: float
    avg_prediction_accuracy_pct: Optional[float]
    events_by_category: dict[str, int]
    top_affected_corridors: List[dict]
    avg_delay_by_category: dict[str, float]


# ─── Full event detail (combines all related objects) ────────────────────────

class EventDetailOut(BaseModel):
    event: EventOut
    prediction: Optional[PredictionOut] = None
    resources: Optional[ResourceOut] = None
    diversion_routes: List[DiversionRouteOut] = []
    advisory: Optional[AdvisoryOut] = None
    feedback: Optional[FeedbackOut] = None

    model_config = {"from_attributes": True}


# ─── Corridors ───────────────────────────────────────────────────────────────

class CorridorOut(BaseModel):
    id: UUID
    corridor_name: str
    latitude: float
    longitude: float
    historical_incident_count: int
    zone: Optional[str]

    model_config = {"from_attributes": True}

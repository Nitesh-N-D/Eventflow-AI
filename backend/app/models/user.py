import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String, Boolean, Integer, Numeric, Text, ARRAY,
    ForeignKey, CheckConstraint, Enum as SAEnum,
    func, TIMESTAMP
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from geoalchemy2 import Geography
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        SAEnum("admin", "traffic_officer", "public_user", name="user_role"),
        nullable=False, default="public_user"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    events: Mapped[List["Event"]] = relationship("Event", back_populates="created_by", lazy="select")


class Corridor(Base):
    __tablename__ = "corridors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    corridor_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    centroid_location: Mapped[object] = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    historical_incident_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    zone: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    point: Mapped[object] = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text)
    nearest_corridor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("corridors.id", ondelete="SET NULL"))
    distance_to_corridor_km: Mapped[Optional[float]] = mapped_column(Numeric(6, 3))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    nearest_corridor: Mapped[Optional["Corridor"]] = relationship("Corridor", lazy="select")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(
        SAEnum("political_rally", "festival", "sports_event", "construction",
               "accident", "emergency_gathering", name="event_category"),
        nullable=False
    )
    location_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id", ondelete="RESTRICT"), nullable=False)
    expected_crowd_size: Mapped[str] = mapped_column(
        SAEnum("low", "medium", "high", "extreme", name="crowd_size_level"),
        nullable=False
    )
    weather_condition: Mapped[Optional[str]] = mapped_column(String(100))
    start_datetime: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    end_datetime: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    affected_roads: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    status: Mapped[str] = mapped_column(
        SAEnum("upcoming", "active", "completed", "cancelled", name="event_status"),
        nullable=False, default="upcoming"
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    location: Mapped["Location"] = relationship("Location", lazy="select")
    created_by: Mapped["User"] = relationship("User", back_populates="events", lazy="select")
    predictions: Mapped[List["Prediction"]] = relationship("Prediction", back_populates="event", lazy="select")
    resources: Mapped[List["Resource"]] = relationship("Resource", back_populates="event", lazy="select")
    diversion_routes: Mapped[List["DiversionRoute"]] = relationship("DiversionRoute", back_populates="event", lazy="select")
    advisory: Mapped[Optional["PublicAdvisory"]] = relationship("PublicAdvisory", back_populates="event", uselist=False, lazy="select")
    feedback: Mapped[Optional["PostEventFeedback"]] = relationship("PostEventFeedback", back_populates="event", uselist=False, lazy="select")


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    congestion_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    traffic_level: Mapped[str] = mapped_column(
        SAEnum("low", "medium", "high", "critical", name="traffic_level"),
        nullable=False
    )
    predicted_duration_minutes: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    predicted_delay_minutes: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    affected_radius_km: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    severity_score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)
    model_r2_duration: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    model_r2_severity: Mapped[Optional[float]] = mapped_column(Numeric(5, 4))
    rare_category_low_confidence: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    input_features_used: Mapped[dict] = mapped_column(JSONB, nullable=False)
    data_provenance: Mapped[str] = mapped_column(String(50), nullable=False, default="real_historical_astram_event_log")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    event: Mapped["Event"] = relationship("Event", back_populates="predictions", lazy="select")


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    prediction_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("predictions.id", ondelete="SET NULL"))
    recommended_officer_count: Mapped[int] = mapped_column(Integer, nullable=False)
    recommended_ambulance_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recommended_control_room_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    barricade_point_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    barricade_spacing_km: Mapped[Optional[float]] = mapped_column(Numeric(6, 3))
    estimated_footprint_km: Mapped[Optional[float]] = mapped_column(Numeric(6, 3))
    historical_road_closure_rate: Mapped[Optional[float]] = mapped_column(Numeric(4, 3))
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    actual_officer_count_deployed: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())

    event: Mapped["Event"] = relationship("Event", back_populates="resources", lazy="select")


class DiversionRoute(Base):
    __tablename__ = "diversion_routes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    alternate_corridor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("corridors.id", ondelete="CASCADE"), nullable=False)
    distance_km: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    historical_total_incidents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_delay_minutes: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    route_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    event: Mapped["Event"] = relationship("Event", back_populates="diversion_routes", lazy="select")
    alternate_corridor: Mapped["Corridor"] = relationship("Corridor", lazy="select")


class TrafficHistory(Base):
    __tablename__ = "traffic_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    corridor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("corridors.id", ondelete="SET NULL"))
    event_cause: Mapped[str] = mapped_column(String(100), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    duration_minutes: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    required_road_closure: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    priority: Mapped[Optional[str]] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="astram_real_dataset")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    corridor: Mapped[Optional["Corridor"]] = relationship("Corridor", lazy="select")


class PublicAdvisory(Base):
    __tablename__ = "public_advisories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    sms_text: Mapped[str] = mapped_column(Text, nullable=False)
    notification_text: Mapped[str] = mapped_column(Text, nullable=False)
    display_board_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    event: Mapped["Event"] = relationship("Event", back_populates="advisory", lazy="select")


class PostEventFeedback(Base):
    __tablename__ = "post_event_feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, unique=True)
    prediction_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("predictions.id", ondelete="CASCADE"), nullable=False)
    actual_duration_minutes: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    actual_delay_minutes: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    actual_officer_count_used: Mapped[Optional[int]] = mapped_column(Integer)
    actual_congestion_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    duration_prediction_error_minutes: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    delay_prediction_error_minutes: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    submitted_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    event: Mapped["Event"] = relationship("Event", back_populates="feedback", lazy="select")

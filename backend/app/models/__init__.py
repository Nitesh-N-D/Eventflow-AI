# Import all models here so SQLAlchemy's metadata.create_all() discovers them
from app.models.user import (  # noqa: F401
    User, Corridor, Location, Event, Prediction,
    Resource, DiversionRoute, TrafficHistory,
    PublicAdvisory, PostEventFeedback,
)

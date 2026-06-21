from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from typing import List, Optional
import uuid

from app.core.database import get_db
from app.core.security import get_current_user, require_officer_or_admin
from app.models.user import User, Event, Location, Prediction, Resource, DiversionRoute, Corridor, PublicAdvisory
from app.schemas.schemas import EventCreate, EventOut, EventDetailOut, PredictionOut

router = APIRouter(prefix="/events", tags=["events"])


async def _find_nearest_corridor(lat: float, lon: float, db: AsyncSession):
    """Find the nearest real Bengaluru corridor using PostGIS ST_Distance."""
    result = await db.execute(
        """
        SELECT id, corridor_name, zone,
               ST_Distance(centroid_location, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) / 1000.0 AS dist_km
        FROM corridors
        ORDER BY dist_km ASC
        LIMIT 1
        """,
        {"lat": lat, "lon": lon}
    )
    row = result.mappings().first()
    return row


async def _trigger_prediction_and_save(event: Event, db: AsyncSession):
    """Called after event creation. Runs real ML pipeline and saves all outputs."""
    from app.ml.prediction_engine import run_full_prediction

    result = run_full_prediction(
        category=event.category,
        latitude=0.0,
        longitude=0.0,
        crowd_size=event.expected_crowd_size,
        start_datetime=event.start_datetime,
        end_datetime=event.end_datetime,
        weather_condition=event.weather_condition,
    )

    # Save prediction
    pred = Prediction(
        event_id=event.id,
        **{k: v for k, v in result["prediction"].items()},
    )
    db.add(pred)
    await db.flush()

    # Save resources
    res = Resource(
        event_id=event.id,
        prediction_id=pred.id,
        **result["resources"],
    )
    db.add(res)

    # Save diversion routes
    for route in result["diversion_routes"]:
        corridor_result = await db.execute(
            select(Corridor).where(Corridor.corridor_name == route["corridor_name"])
        )
        corridor = corridor_result.scalar_one_or_none()
        if corridor:
            dr = DiversionRoute(
                event_id=event.id,
                alternate_corridor_id=corridor.id,
                distance_km=route["distance_km"],
                historical_total_incidents=route.get("historical_total_incidents", 0),
                estimated_delay_minutes=route.get("estimated_delay_minutes"),
                route_rank=route["route_rank"],
            )
            db.add(dr)

    # Save public advisory (update event name placeholder)
    advisories = result["advisories"]
    for key in advisories:
        advisories[key] = advisories[key].replace("on  on", f"on {event.event_name} on")
    adv = PublicAdvisory(event_id=event.id, **advisories)
    db.add(adv)

    await db.commit()


@router.post("/", response_model=EventOut, status_code=status.HTTP_201_CREATED)
async def create_event(
    body: EventCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_officer_or_admin),
):
    # Create location
    loc = Location(
        point=f"SRID=4326;POINT({body.longitude} {body.latitude})",
        address=body.address,
    )
    db.add(loc)
    await db.flush()

    # Create event
    event = Event(
        event_name=body.event_name,
        category=body.category,
        location_id=loc.id,
        expected_crowd_size=body.expected_crowd_size,
        weather_condition=body.weather_condition,
        start_datetime=body.start_datetime,
        end_datetime=body.end_datetime,
        affected_roads=body.affected_roads,
        created_by_id=current_user.id,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event, ["location"])

    # Run AI prediction in background so the create endpoint responds immediately
    background_tasks.add_task(_trigger_prediction_and_save, event, db)

    return event


@router.get("/", response_model=List[EventOut])
async def list_events(
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(Event).options(selectinload(Event.location)).order_by(desc(Event.created_at)).limit(limit).offset(offset)
    if status_filter:
        q = q.where(Event.status == status_filter)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{event_id}", response_model=EventDetailOut)
async def get_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Event)
        .options(
            selectinload(Event.location),
            selectinload(Event.predictions),
            selectinload(Event.resources),
            selectinload(Event.diversion_routes).selectinload(DiversionRoute.alternate_corridor),
            selectinload(Event.advisory),
            selectinload(Event.feedback),
        )
        .where(Event.id == event_id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Build diversion route output with corridor name
    diversion_out = []
    for dr in (event.diversion_routes or []):
        diversion_out.append({
            "id": dr.id,
            "alternate_corridor_id": dr.alternate_corridor_id,
            "corridor_name": dr.alternate_corridor.corridor_name if dr.alternate_corridor else "Unknown",
            "distance_km": float(dr.distance_km),
            "historical_total_incidents": dr.historical_total_incidents,
            "estimated_delay_minutes": float(dr.estimated_delay_minutes) if dr.estimated_delay_minutes else None,
            "route_rank": dr.route_rank,
        })

    latest_prediction = event.predictions[-1] if event.predictions else None
    latest_resource = event.resources[-1] if event.resources else None

    return EventDetailOut(
        event=event,
        prediction=latest_prediction,
        resources=latest_resource,
        diversion_routes=diversion_out,
        advisory=event.advisory,
        feedback=event.feedback,
    )


@router.patch("/{event_id}/status")
async def update_event_status(
    event_id: uuid.UUID,
    new_status: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_officer_or_admin),
):
    valid_statuses = {"upcoming", "active", "completed", "cancelled"}
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Status must be one of {valid_statuses}")
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    event.status = new_status
    await db.commit()
    return {"id": event_id, "status": new_status}

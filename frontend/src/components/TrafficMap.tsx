import { useEffect, useRef } from "react";
import type { EventOut, DiversionRoute, Corridor } from "../types";

interface Props {
  event?: EventOut;
  corridors?: Corridor[];
  diversionRoutes?: DiversionRoute[];
  height?: string;
}

declare global {
  interface Window { L: typeof import("leaflet"); }
}

export default function TrafficMap({ event, corridors = [], diversionRoutes = [], height = "400px" }: Props) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);

  useEffect(() => {
    if (!mapRef.current || mapInstanceRef.current) return;
    const L = window.L;
    if (!L) return;

    const map = L.map(mapRef.current).setView([12.9716, 77.5946], 11);
    mapInstanceRef.current = map;

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap contributors",
    }).addTo(map);

    // Plot real ASTRAM corridors with incident-load color
    corridors.forEach((c) => {
      const maxCount = Math.max(...corridors.map(x => x.historical_incident_count), 1);
      const intensity = c.historical_incident_count / maxCount;
      const color = intensity > 0.7 ? "#ef4444" : intensity > 0.4 ? "#f59e0b" : "#10b981";

      L.circleMarker([c.latitude, c.longitude], {
        radius: 8 + intensity * 12,
        fillColor: color, color: color, fillOpacity: 0.5, weight: 2,
      }).addTo(map).bindPopup(
        `<div style="font-family:Inter;min-width:160px">
          <strong style="color:${color}">${c.corridor_name}</strong><br/>
          <span style="color:#64748b">Zone: ${c.zone || "—"}</span><br/>
          <span style="color:#64748b">Historical incidents: ${c.historical_incident_count}</span>
        </div>`
      );
    });

    // Plot event location
    if (event) {
      L.circleMarker([12.9716, 77.5946], {
        radius: 16, fillColor: "#3b82f6", color: "#3b82f6", fillOpacity: 0.3, weight: 3,
      }).addTo(map).bindPopup(
        `<strong>${event.event_name}</strong><br/>${event.category.replace("_", " ")}`
      ).openPopup();
    }

    // Plot diversion routes
    diversionRoutes.forEach((dr) => {
      const match = corridors.find(c => c.id === dr.alternate_corridor_id);
      if (match) {
        L.circleMarker([match.latitude, match.longitude], {
          radius: 10, fillColor: "#10b981", color: "#10b981", fillOpacity: 0.6, weight: 2,
        }).addTo(map).bindPopup(
          `<strong>Route ${dr.route_rank}</strong>: ${dr.corridor_name}<br/>
           Delay: ${dr.estimated_delay_minutes?.toFixed(0) ?? "—"} min`
        );
      }
    });

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, [corridors, event, diversionRoutes]);

  return (
    <div
      ref={mapRef}
      className="map-dark rounded-xl overflow-hidden border border-border"
      style={{ height }}
    />
  );
}

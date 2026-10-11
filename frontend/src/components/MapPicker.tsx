import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// ERA5 on Open-Meteo is a ~0.25 degree grid; outline the cell actually analyzed.
const HALF_CELL = 0.125;

export default function MapPicker({
  latitude,
  longitude,
  grid,
  disabled,
  onPick,
}: {
  latitude: number;
  longitude: number;
  grid: { latitude: number; longitude: number } | null;
  disabled: boolean;
  onPick: (latitude: number, longitude: number) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const marker = useRef<L.CircleMarker | null>(null);
  const cell = useRef<L.Rectangle | null>(null);
  const pick = useRef(onPick);
  const locked = useRef(disabled);
  pick.current = onPick;
  locked.current = disabled;

  useEffect(() => {
    if (!container.current) return;
    const instance = L.map(container.current, { worldCopyJump: true }).setView(
      [latitude, longitude],
      5,
    );
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 12,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(instance);
    instance.on("click", (event: L.LeafletMouseEvent) => {
      if (locked.current) return;
      const { lat, lng } = event.latlng.wrap();
      pick.current(Number(lat.toFixed(2)), Number(lng.toFixed(2)));
    });
    map.current = instance;
    return () => {
      instance.remove();
      map.current = null;
      marker.current = null;
      cell.current = null;
    };
    // Created once; later coordinate changes are applied by the effects below.
  }, []);

  useEffect(() => {
    const instance = map.current;
    if (!instance || !Number.isFinite(latitude) || !Number.isFinite(longitude))
      return;
    if (Math.abs(latitude) > 90 || Math.abs(longitude) > 180) return;
    marker.current ??= L.circleMarker([latitude, longitude], {
      radius: 7,
      color: "#1f5c4c",
      fillColor: "#28735f",
      fillOpacity: 0.9,
    }).addTo(instance);
    marker.current.setLatLng([latitude, longitude]);
    if (!instance.getBounds().contains([latitude, longitude]))
      instance.panTo([latitude, longitude]);
  }, [latitude, longitude]);

  useEffect(() => {
    const instance = map.current;
    cell.current?.remove();
    cell.current = null;
    if (!instance || !grid) return;
    cell.current = L.rectangle(
      [
        [grid.latitude - HALF_CELL, grid.longitude - HALF_CELL],
        [grid.latitude + HALF_CELL, grid.longitude + HALF_CELL],
      ],
      { color: "#b66635", weight: 2, fill: false, dashArray: "4 4" },
    ).addTo(instance);
  }, [grid]);

  return (
    <div className="map-field">
      <div
        ref={container}
        className="map"
        role="application"
        aria-label="Map. Click to choose the analysis point; coordinates can also be typed below."
      />
      <small>
        Click the map to pick a point.
        {grid && " Dashed square: the ERA5 grid cell used for the last result."}
      </small>
    </div>
  );
}

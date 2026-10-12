import { useState } from "react";
import { CircleMarker, MapContainer, Rectangle, TileLayer, useMapEvents } from "react-leaflet";
import type { LatLng, LatLngBoundsExpression } from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Region } from "../types";

type Tool = "point" | "box";
type Box = { minLon: number; minLat: number; maxLon: number; maxLat: number };

const CENTER: [number, number] = [16.5, 79.7]; // Andhra Pradesh / Telangana
const MAX_BOX_DEGREES = 2; // mirrors backend/app/schemas.py
const GRID_STEP = 0.25; // ERA5 grid, mirrors backend/app/services/grid.py
const STYLE = { color: "#c2410c", weight: 2, fillOpacity: 0.12 };
const TOO_BIG_STYLE = { color: "#5d6676", weight: 2, fillOpacity: 0.08, dashArray: "4" };

const round3 = (n: number) => Math.round(n * 1000) / 1000;
const snap = (n: number) => Math.round(n / GRID_STEP) * GRID_STEP;

function toBox(a: LatLng, b: LatLng): Box {
  return {
    minLon: round3(Math.min(a.lng, b.lng)),
    minLat: round3(Math.min(a.lat, b.lat)),
    maxLon: round3(Math.max(a.lng, b.lng)),
    maxLat: round3(Math.max(a.lat, b.lat)),
  };
}

const tooBig = (b: Box) => b.maxLon - b.minLon > MAX_BOX_DEGREES || b.maxLat - b.minLat > MAX_BOX_DEGREES;
const bounds = (b: Box): LatLngBoundsExpression => [[b.minLat, b.minLon], [b.maxLat, b.maxLon]];

function MapEvents({ onClick, onMove }: { onClick: (p: LatLng) => void; onMove?: (p: LatLng) => void }) {
  useMapEvents({
    click: (e) => onClick(e.latlng.wrap()),
    mousemove: (e) => onMove?.(e.latlng.wrap()),
  });
  return null;
}

interface Props {
  value: Region | null;
  onPick: (r: Region) => void;
}

export function MapSelector({ value, onPick }: Props) {
  const [tool, setTool] = useState<Tool>("point");
  const [corner, setCorner] = useState<LatLng | null>(null);
  const [hover, setHover] = useState<LatLng | null>(null);
  const [error, setError] = useState<string | null>(null);

  const switchTool = (t: Tool) => {
    setTool(t);
    setCorner(null);
    setHover(null);
    setError(null);
  };

  const handleClick = (p: LatLng) => {
    setError(null);
    if (tool === "point") {
      const lat = round3(p.lat), lon = round3(p.lng);
      onPick({ kind: "point", lat, lon, label: `Map point ${lat}, ${lon}` });
      return;
    }
    if (!corner) {
      setCorner(p);
      setHover(p);
      return;
    }
    const box = toBox(corner, p);
    setCorner(null);
    setHover(null);
    if (box.minLon === box.maxLon || box.minLat === box.maxLat) {
      setError("The two corners are the same point. Click two different corners.");
    } else if (tooBig(box)) {
      setError(`Box is larger than ${MAX_BOX_DEGREES}° × ${MAX_BOX_DEGREES}°. Draw a smaller one.`);
    } else {
      onPick({ kind: "bbox", ...box, label: `Map box ${box.minLat},${box.minLon} → ${box.maxLat},${box.maxLon}` });
    }
  };

  const preview = corner && hover ? toBox(corner, hover) : null;
  // The ERA5 cell a point snaps to: this is the area the data actually describes.
  const cell = value?.kind === "point"
    ? { minLat: snap(value.lat) - GRID_STEP / 2, maxLat: snap(value.lat) + GRID_STEP / 2,
        minLon: snap(value.lon) - GRID_STEP / 2, maxLon: snap(value.lon) + GRID_STEP / 2 }
    : null;

  return (
    <div>
      <div className="tabs">
        {(["point", "box"] as Tool[]).map((t) => (
          <button key={t} type="button" aria-pressed={tool === t}
            className={tool === t ? "tab active" : "tab"} onClick={() => switchTool(t)}>
            {t === "point" ? "Click a point" : "Draw a box"}
          </button>
        ))}
      </div>
      <MapContainer center={CENTER} zoom={6} minZoom={2} className="map" worldCopyJump>
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        />
        <MapEvents onClick={handleClick} onMove={corner ? setHover : undefined} />
        {value?.kind === "point" && <CircleMarker center={[value.lat, value.lon]} radius={6} pathOptions={STYLE} />}
        {cell && <Rectangle bounds={bounds(cell)} pathOptions={STYLE} />}
        {value?.kind === "bbox" && !corner && <Rectangle bounds={bounds(value)} pathOptions={STYLE} />}
        {preview && <Rectangle bounds={bounds(preview)} pathOptions={tooBig(preview) ? TOO_BIG_STYLE : STYLE} />}
      </MapContainer>
      {error && <p className="error small">{error}</p>}
      <p className="muted small">
        {tool === "point"
          ? "Click anywhere. The square is the ~25 km ERA5 grid cell the data comes from."
          : corner
            ? "Now click the opposite corner."
            : `Click two opposite corners. Max ${MAX_BOX_DEGREES}° × ${MAX_BOX_DEGREES}°, averaged over up to 25 grid cells.`}
      </p>
    </div>
  );
}

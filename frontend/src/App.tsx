import { useState, useRef, useEffect } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";

mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN;

const YEARS = [1900, 1914, 1920, 1930, 1938, 1945, 1960, 1994, 2000];

// Named colors for major powers, HOI4-inspired
const NAMED_COLORS: Record<string, string> = {
  "German Empire": "#5a5a3c",
  Germany: "#5a5a3c",
  "Nazi Germany": "#4a4a2e",
  "West Germany": "#6b7c4a",
  "East Germany": "#4a5a3c",
  France: "#3a5fa0",
  "French Republic": "#3a5fa0",
  "United Kingdom of Great Britain and Ireland": "#c1243c",
  "United Kingdom": "#c1243c",
  "Great Britain": "#c1243c",
  Russia: "#8b1a1a",
  "Soviet Union": "#8b1a1a",
  USSR: "#8b1a1a",
  "Austria-Hungary": "#c8922a",
  Austria: "#c8922a",
  "Kingdom of Italy": "#3d7a3d",
  Italy: "#3d7a3d",
  "Ottoman Empire": "#2d6b5a",
  Turkey: "#2d6b5a",
  Spain: "#c8601a",
  "Kingdom of Spain": "#c8601a",
  Poland: "#8b3a5a",
  Czechoslovakia: "#4a6b8b",
  Yugoslavia: "#5a3a8b",
  "Kingdom of Yugoslavia": "#5a3a8b",
  Romania: "#8b7a2a",
  Hungary: "#6b3a2a",
  Bulgaria: "#4a6b4a",
  Greece: "#2a5a8b",
  Sweden: "#2a4a8b",
  Norway: "#7a2a3a",
  Denmark: "#8b2a2a",
  Belgium: "#8b7a00",
  Netherlands: "#c87a2a",
  Switzerland: "#8b2a2a",
  Portugal: "#2a6b3a",
  Serbia: "#5a2a6b",
};

const HOI4_PALETTE = [
  "#5a6b3c",
  "#3a5a8b",
  "#8b3a3a",
  "#6b5a2a",
  "#3a6b5a",
  "#6b3a6b",
  "#3a6b3a",
  "#8b6b2a",
  "#3a4a8b",
  "#6b2a3a",
  "#4a6b6b",
  "#8b5a3a",
  "#4a3a8b",
  "#6b8b3a",
  "#2a5a6b",
  "#8b4a5a",
  "#5a8b3a",
  "#3a8b6b",
  "#6b4a3a",
  "#4a5a6b",
];

function countryColor(name: string): string {
  if (NAMED_COLORS[name]) return NAMED_COLORS[name];
  let hash = 0;
  for (let i = 0; i < name.length; i++)
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return HOI4_PALETTE[Math.abs(hash) % HOI4_PALETTE.length];
}

function buildColorExpression(
  features: { properties: { name: string } }[],
): unknown[] {
  const expr: unknown[] = ["match", ["get", "name"]];
  const seen = new Set<string>();
  features.forEach((f) => {
    if (!seen.has(f.properties.name)) {
      expr.push(f.properties.name, countryColor(f.properties.name));
      seen.add(f.properties.name);
    }
  });
  expr.push("#6b6b5a"); // fallback
  return expr;
}

const GENERIC_WORDS = new Set([
  "kingdom",
  "empire",
  "republic",
  "united",
  "great",
  "north",
  "south",
  "east",
  "west",
  "state",
  "states",
  "land",
  "lands",
  "holy",
  "federal",
  "democratic",
  "peoples",
  "soviet",
]);

function matchRegions(
  regions: string[],
  features: { properties: { name: string } }[],
): string[] {
  const names = features.map((f) => f.properties.name);
  const matched = names.filter((n) => {
    const nl = n.toLowerCase();
    return regions.some((r) => {
      const rl = r.toLowerCase();
      if (nl.includes(rl) || rl.includes(nl)) return true;
      // word-level stem: "German Empire" ↔ "Germany" via "german", but skip generic words
      const significantWords = nl
        .split(/\s+/)
        .filter((w) => w.length > 4 && !GENERIC_WORDS.has(w));
      return significantWords.some((w) => rl.includes(w));
    });
  });
  return matched.length > 0 ? matched : regions;
}

interface Moment {
  year: number;
  title: string;
  description: string;
  regions: string[];
}
interface QueryResponse {
  answer: string;
  regions: string[];
  year_start: number;
  year_end: number;
  moments: Moment[];
  citations: string[];
}

export default function App() {
  const [year, setYear] = useState(1914);
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<mapboxgl.Map | null>(null);
  const mapLoaded = useRef(false);
  const colorsExpression = useRef<unknown[]>([
    "match",
    ["get", "name"],
    "#6b6b5a",
  ]);
  const currentFeatures = useRef<
    {
      properties: { name: string };
      geometry: { coordinates: number[][][][] };
    }[]
  >([]);
  const pendingRegions = useRef<string[] | null>(null);
  const activeRegions = useRef<string[] | null>(null);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [displayedAnswer, setDisplayedAnswer] = useState("");
  const [currentMoment, setCurrentMoment] = useState<Moment | null>(null);
  const [momentIdx, setMomentIdx] = useState(-1);
  const [highlightTrigger, setHighlightTrigger] = useState(0);

  function handleReset() {
    setResult(null);
    setDisplayedAnswer("");
    setMomentIdx(-1);
    setCurrentMoment(null);
    activeRegions.current = null;
    pendingRegions.current = null;
    const map = mapInstance.current;
    if (map && map.getLayer("borders-fill")) {
      map.setPaintProperty(
        "borders-fill",
        "fill-color",
        colorsExpression.current as mapboxgl.Expression,
      );
      map.setPaintProperty("borders-fill", "fill-opacity", 0.85);
    }
  }

  function jumpToMoment(moment: Moment) {
    setCurrentMoment(moment);
    activeRegions.current = moment.regions;
    const targetYear = YEARS.find((y) => y >= moment.year) ?? moment.year;
    setYear(targetYear as number);
    pendingRegions.current = moment.regions;
    setHighlightTrigger((t) => t + 1);
  }

  function handleQuery() {
    setLoading(true);
    setResult(null);
    setDisplayedAnswer("");
    setMomentIdx(-1);
    setCurrentMoment(null);
    fetch("http://localhost:8000/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: query }),
    })
      .then((r) => r.json())
      .then((data) => {
        setResult(data);
        setLoading(false);
        if (data.moments.length > 0) {
          setMomentIdx(0);
          jumpToMoment(data.moments[0]);
        }
        let i = 0;
        const interval = setInterval(() => {
          i++;
          setDisplayedAnswer(data.answer.slice(0, i));
          if (i >= data.answer.length) clearInterval(interval);
        }, 12);
      });
  }

  function handleContinue() {
    if (!result) return;
    const nextIdx = momentIdx + 1;
    if (nextIdx >= result.moments.length) return;
    setMomentIdx(nextIdx);
    jumpToMoment(result.moments[nextIdx]);
  }

  useEffect(() => {
    const map = mapInstance.current;
    // highlight handled in year effect via pendingRegions
  }, [result]);

  function applyHighlight(map: mapboxgl.Map, regions: string[]) {
    if (!map.getLayer("borders-fill")) return;
    try {
      const matched = matchRegions(regions, currentFeatures.current);
      map.setPaintProperty(
        "borders-fill",
        "fill-color",
        colorsExpression.current as mapboxgl.Expression,
      );
      map.setPaintProperty("borders-fill", "fill-opacity", [
        "case",
        ["in", ["get", "name"], ["literal", matched]],
        0.9,
        0.12,
      ] as mapboxgl.Expression);
      const highlighted = currentFeatures.current.filter((f) =>
        matched.includes(f.properties.name),
      );
      if (highlighted.length > 0) {
        const bounds = new mapboxgl.LngLatBounds();
        highlighted.forEach((f) =>
          f.geometry.coordinates.forEach((polygon: number[][][]) =>
            polygon.forEach((ring) =>
              ring.forEach(([lng, lat]: number[]) => {
                if (lng >= -30 && lng <= 65 && lat >= 25 && lat <= 75)
                  bounds.extend([lng, lat]);
              }),
            ),
          ),
        );
        map.fitBounds(bounds, { padding: 80, maxZoom: 6, duration: 2500 });
      }
    } catch (e) {
      console.warn("highlight failed", e);
    }
  }

  useEffect(() => {
    const map = new mapboxgl.Map({
      container: mapRef.current!,
      style: "mapbox://styles/mapbox/empty-v9",
      center: [15, 50],
      zoom: 4,
      minZoom: 3,
      maxZoom: 10,
      maxBounds: [
        [-30, 25],
        [65, 75],
      ], // Europe bounds
      projection: "mercator",
    });
    mapInstance.current = map;
    map.on("load", () => {
      mapLoaded.current = true;
      map.addSource("hillshade", {
        type: "raster-dem",
        url: "mapbox://mapbox.mapbox-terrain-dem-v1",
        tileSize: 512,
      });
      map.addLayer({
        id: "hillshade-layer",
        type: "hillshade",
        source: "hillshade",
        paint: {
          "hillshade-intensity": 0.5,
          "hillshade-shadow-color": "#473B24",
        },
      });
      fetch("http://localhost:8000/borders/1914")
        .then((r) => r.json())
        .then((geojson) => {
          const expr = buildColorExpression(geojson.features);
          colorsExpression.current = expr;
          map.addSource("borders", { type: "geojson", data: geojson });
          map.addLayer({
            id: "borders-fill",
            type: "fill",
            source: "borders",
            paint: {
              "fill-color": expr as mapboxgl.Expression,
              "fill-opacity": 0.85,
            },
          });
          map.addLayer({
            id: "borders-line",
            type: "line",
            source: "borders",
            paint: { "line-color": "#1a1a0f", "line-width": 0.6 },
          });
          map.addLayer({
            id: "borders-label",
            type: "symbol",
            source: "borders",
            layout: {
              "text-field": ["get", "name"],
              "text-size": 11,
              "text-font": ["Open Sans Bold", "Arial Unicode MS Bold"],
              "text-max-width": 8,
            },
            paint: {
              "text-color": "#ffffff",
              "text-halo-color": "#000000",
              "text-halo-width": 1,
            },
          });
        });
    });
    const observer = new ResizeObserver(() => map.resize());
    if (mapRef.current) observer.observe(mapRef.current);
    return () => {
      observer.disconnect();
      mapLoaded.current = false;
      map.remove();
    };
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleReset();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [result]);

  useEffect(() => {
    const map = mapInstance.current;
    if (!map || !map.getSource("borders")) return;
    let cancelled = false;
    fetch(`http://localhost:8000/borders/${year}`)
      .then((r) => r.json())
      .then((geojson) => {
        if (cancelled) return;
        currentFeatures.current = geojson.features;
        const expr = buildColorExpression(geojson.features);
        colorsExpression.current = expr;
        (map.getSource("borders") as mapboxgl.GeoJSONSource).setData(geojson);
        if (pendingRegions.current) {
          applyHighlight(map, pendingRegions.current);
          pendingRegions.current = null;
        } else if (activeRegions.current) {
          const matched = matchRegions(activeRegions.current, geojson.features);
          if (map.getLayer("borders-fill")) {
            map.setPaintProperty(
              "borders-fill",
              "fill-color",
              colorsExpression.current as mapboxgl.Expression,
            );
            map.setPaintProperty("borders-fill", "fill-opacity", [
              "case",
              ["in", ["get", "name"], ["literal", matched]],
              0.9,
              0.12,
            ] as mapboxgl.Expression);
          }
        } else if (map.getLayer("borders-fill")) {
          map.setPaintProperty(
            "borders-fill",
            "fill-color",
            expr as mapboxgl.Expression,
          );
          map.setPaintProperty("borders-fill", "fill-opacity", 0.85);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [year, highlightTrigger]);

  return (
    <div
      style={{
        position: "relative",
        width: "100vw",
        height: "100vh",
        backgroundColor: "#0a1628",
      }}
    >
      <div
        ref={mapRef}
        style={{
          width: result || loading ? "calc(100% - 380px)" : "100%",
          height: "100%",
          transition: "width 0.3s",
        }}
        onTransitionEnd={() => mapInstance.current?.resize()}
      />

      {/* query input */}
      <div
        style={{
          position: "absolute",
          top: 20,
          left: "50%",
          transform: "translateX(-50%)",
          zIndex: 10,
          display: "flex",
          gap: 8,
        }}
      >
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleQuery()}
          placeholder="Ask about European history..."
          style={{
            width: 400,
            padding: "8px 12px",
            borderRadius: 4,
            border: "none",
            fontSize: 14,
          }}
        />
        <button
          onClick={handleQuery}
          style={{
            padding: "8px 16px",
            borderRadius: 4,
            border: "none",
            background: "#e8613c",
            color: "white",
            cursor: "pointer",
          }}
        >
          {loading ? "Loading..." : "Ask"}
        </button>
      </div>

      {/* result panel */}
      {(result || loading) && (
        <div
          style={{
            position: "absolute",
            top: 0,
            right: 0,
            height: "100vh",
            width: "380px",
            backgroundColor: "#0f1923",
            color: "#e8e0d0",
            display: "flex",
            flexDirection: "column",
            borderLeft: "1px solid #2a3a4a",
            zIndex: 10,
            overflowY: "auto",
          }}
        >
          <div style={{ padding: "20px 20px 0" }}>
            {loading && (
              <p
                style={{ color: "#6a8a9a", fontStyle: "italic", fontSize: 13 }}
              >
                Thinking...
              </p>
            )}
            <p style={{ fontSize: 13, lineHeight: 1.7, color: "#c8c0b0" }}>
              {displayedAnswer}
            </p>
          </div>
          {result && (
            <>
              <div
                style={{
                  margin: "16px 20px 0",
                  padding: "12px 0",
                  borderTop: "1px solid #2a3a4a",
                }}
              >
                <span
                  style={{
                    fontSize: 11,
                    color: "#6a8a9a",
                    textTransform: "uppercase",
                    letterSpacing: 1,
                  }}
                >
                  {result.year_start} — {result.year_end}
                </span>
              </div>
              <div style={{ padding: "0 20px" }}>
                <p
                  style={{
                    fontSize: 11,
                    color: "#6a8a9a",
                    textTransform: "uppercase",
                    letterSpacing: 1,
                    marginBottom: 8,
                  }}
                >
                  Key Moments
                </p>
                {result.moments.map((m, idx) => (
                  <div
                    key={idx}
                    style={{
                      marginBottom: 12,
                      paddingLeft: 12,
                      borderLeft: `2px solid ${idx === momentIdx ? "#ffffff" : "#e8613c"}`,
                      backgroundColor:
                        idx === momentIdx
                          ? "rgba(255,255,255,0.08)"
                          : "transparent",
                      opacity: idx > momentIdx ? 0.35 : 1,
                      transition:
                        "background-color 0.5s, border-color 0.5s, opacity 0.5s",
                    }}
                  >
                    <div
                      style={{
                        fontSize: 12,
                        color: "#e8613c",
                        fontWeight: 600,
                      }}
                    >
                      {m.year} · {m.title}
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        color: "#a0a8b0",
                        marginTop: 2,
                        lineHeight: 1.5,
                      }}
                    >
                      {m.description}
                    </div>
                  </div>
                ))}
              </div>
              {momentIdx < result.moments.length - 1 && (
                <div style={{ padding: "8px 20px" }}>
                  <button
                    onClick={handleContinue}
                    style={{
                      width: "100%",
                      padding: "8px",
                      background: "#1a2a3a",
                      border: "1px solid #e8613c",
                      color: "#e8613c",
                      borderRadius: 4,
                      cursor: "pointer",
                      fontSize: 13,
                    }}
                  >
                    Continue →
                  </button>
                </div>
              )}
              <div
                style={{
                  padding: "12px 20px 20px",
                  borderTop: "1px solid #2a3a4a",
                  marginTop: 8,
                }}
              >
                <p
                  style={{
                    fontSize: 11,
                    color: "#6a8a9a",
                    textTransform: "uppercase",
                    letterSpacing: 1,
                    marginBottom: 8,
                  }}
                >
                  Sources
                </p>
                {result.citations.map((c, idx) => (
                  <div
                    key={idx}
                    style={{ fontSize: 12, color: "#6a8a9a", marginBottom: 4 }}
                  >
                    · {c}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* close/reset button on panel */}
      {(result || loading) && (
        <button
          onClick={() => {
            setResult(null);
            setDisplayedAnswer("");
            setMomentIdx(-1);
            setCurrentMoment(null);
            activeRegions.current = null;
            pendingRegions.current = null;
            const map = mapInstance.current;
            if (map && map.getLayer("borders-fill")) {
              map.setPaintProperty(
                "borders-fill",
                "fill-color",
                colorsExpression.current as mapboxgl.Expression,
              );
              map.setPaintProperty("borders-fill", "fill-opacity", 0.85);
            }
          }}
          style={{
            position: "absolute",
            top: 20,
            right: 20,
            zIndex: 11,
            padding: "6px 10px",
            background: "#1a2a3a",
            border: "1px solid #e8613c",
            color: "#e8613c",
            borderRadius: 4,
            cursor: "pointer",
          }}
        >
          ×
        </button>
      )}

      {/* slider */}
      <div
        style={{
          position: "absolute",
          bottom: 40,
          left: "50%",
          transform: "translateX(-50%)",
          zIndex: 10,
        }}
      >
        <input
          type="range"
          min={0}
          max={YEARS.length - 1}
          value={YEARS.indexOf(year)}
          onChange={(e) => setYear(YEARS[parseInt(e.target.value)])}
        />
        <div style={{ textAlign: "center", color: "white", fontSize: 24 }}>
          {year}
        </div>
      </div>
    </div>
  );
}

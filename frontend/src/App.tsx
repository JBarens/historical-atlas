import { useState, useRef, useEffect } from "react";
import html2canvas from "html2canvas";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import "./App.css";

mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN;

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const YEARS = [1900, 1914, 1920, 1930, 1938, 1945, 1960, 1994, 2000];

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
  "#5a6b3c", "#3a5a8b", "#8b3a3a", "#6b5a2a", "#3a6b5a",
  "#6b3a6b", "#3a6b3a", "#8b6b2a", "#3a4a8b", "#6b2a3a",
  "#4a6b6b", "#8b5a3a", "#4a3a8b", "#6b8b3a", "#2a5a6b",
  "#8b4a5a", "#5a8b3a", "#3a8b6b", "#6b4a3a", "#4a5a6b",
];

function countryColor(name: string): string {
  if (NAMED_COLORS[name]) return NAMED_COLORS[name];
  let hash = 0;
  for (let i = 0; i < name.length; i++)
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return HOI4_PALETTE[Math.abs(hash) % HOI4_PALETTE.length];
}

function buildColorExpression(features: { properties: { name: string } }[]): unknown[] {
  const expr: unknown[] = ["match", ["get", "name"]];
  const seen = new Set<string>();
  features.forEach((f) => {
    if (!seen.has(f.properties.name)) {
      expr.push(f.properties.name, countryColor(f.properties.name));
      seen.add(f.properties.name);
    }
  });
  expr.push("#6b6b5a");
  return expr;
}

const GENERIC_WORDS = new Set([
  "kingdom", "empire", "republic", "united", "great",
  "north", "south", "east", "west", "state", "states",
  "land", "lands", "holy", "federal", "democratic", "peoples", "soviet",
]);

function matchRegions(regions: string[], features: { properties: { name: string } }[]): string[] {
  const names = features.map((f) => f.properties.name);
  const matched = names.filter((n) => {
    const nl = n.toLowerCase();
    return regions.some((r) => {
      const rl = r.toLowerCase();
      if (nl.includes(rl) || rl.includes(nl)) return true;
      const significantWords = nl.split(/\s+/).filter((w) => w.length > 4 && !GENERIC_WORDS.has(w));
      return significantWords.some((w) => rl.includes(w));
    });
  });
  return matched.length > 0 ? matched : regions;
}

interface CountryFact {
  formal_name: string;
  period: string;
  summary: string;
  key_facts: string[];
  citations: string[];
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

const EXAMPLE_QUERIES = [
  "What caused World War I?",
  "How did Germany divide after 1945?",
  "What happened to Yugoslavia?",
];

export default function App() {
  const [year, setYear] = useState(1914);
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<HTMLDivElement>(null);
  const streamDone = useRef(false);
  const mapInstance = useRef<mapboxgl.Map | null>(null);
  const mapLoaded = useRef(false);
  const colorsExpression = useRef<unknown[]>(["match", ["get", "name"], "#6b6b5a"]);
  const currentFeatures = useRef<{ properties: { name: string }; geometry: { coordinates: number[][][][] } }[]>([]);
  const pendingRegions = useRef<string[] | null>(null);
  const activeRegions = useRef<string[] | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const yearRef = useRef(year);
  const [countryCard, setCountryCard] = useState<CountryFact | null>(null);
  const [countryLoading, setCountryLoading] = useState(false);
  const [countryName, setCountryName] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [displayedAnswer, setDisplayedAnswer] = useState("");
  const [_currentMoment, setCurrentMoment] = useState<Moment | null>(null);
  const [momentIdx, setMomentIdx] = useState(-1);
  const [highlightTrigger, setHighlightTrigger] = useState(0);
  const queue = useRef<string[]>([]);
  const [history, setHistory] = useState<{ id: number; question: string }[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", handler);
    return () => window.removeEventListener("resize", handler);
  }, []);

  function clearInterval_() {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }

  function handleReset() {
    clearInterval_();
    setResult(null);
    setDisplayedAnswer("");
    setMomentIdx(-1);
    setCurrentMoment(null);
    setError(null);
    activeRegions.current = null;
    pendingRegions.current = null;
    queue.current = [];
    const map = mapInstance.current;
    if (map && map.getLayer("borders-fill")) {
      map.setPaintProperty("borders-fill", "fill-color", colorsExpression.current as mapboxgl.Expression);
      map.setPaintProperty("borders-fill", "fill-opacity", 0.85);
    }
    if (map && map.getLayer("borders-label")) {
      map.setPaintProperty("borders-label", "text-opacity", 1);
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

  function handleContinue() {
    if (!result) return;
    const nextIdx = momentIdx + 1;
    if (nextIdx >= result.moments.length) return;
    setMomentIdx(nextIdx);
    jumpToMoment(result.moments[nextIdx]);
  }

  async function handleExport() {
    if (!containerRef.current) return;
    setExporting(true);
    try {
      const canvas = await html2canvas(containerRef.current, {
        useCORS: true,
        allowTaint: false,
        logging: false,
      });
      const link = document.createElement("a");
      link.download = `historical-atlas-${year}.png`;
      link.href = canvas.toDataURL("image/png");
      link.click();
    } finally {
      setExporting(false);
    }
  }

  async function loadHistory() {
    const res = await fetch(`${API_URL}/history`);
    const rows = await res.json();
    setHistory(rows);
    setShowHistory(true);
  }

  async function handleQuery(questionOverride?: string) {
    const q = (questionOverride ?? query).trim();
    if (!q) return;

    clearInterval_();
    setLoading(true);
    setError(null);
    setResult(null);
    setDisplayedAnswer("");
    setMomentIdx(-1);
    setCurrentMoment(null);
    streamDone.current = false;
    queue.current = [];

    try {
      const response = await fetch(`${API_URL}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });

      if (!response.ok) throw new Error(`Server error ${response.status}`);

      const reader = response.body!.getReader();
      const decode = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decode.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() ?? "";
        for (const event of events) {
          if (!event.startsWith("data: ")) continue;
          const msg = JSON.parse(event.slice(6));
          if (msg.type === "meta") {
            intervalRef.current = setInterval(() => {
              if (queue.current.length > 0) {
                const char = queue.current.shift()!;
                setDisplayedAnswer((prev) => prev + char);
              } else if (streamDone.current) {
                clearInterval_();
              }
            }, 20);
            setResult(msg);
            setLoading(false);
            if (msg.moments.length > 0) {
              setMomentIdx(0);
              jumpToMoment(msg.moments[0]);
            }
          } else if (msg.type === "text") {
            queue.current.push(msg.char);
          } else if (msg.type === "done") {
            streamDone.current = true;
          }
        }
      }
    } catch (e) {
      setError("Could not reach the server. Make sure the backend is running.");
    } finally {
      setLoading(false);
    }
  }

  function applyHighlight(map: mapboxgl.Map, regions: string[]) {
    if (!map.getLayer("borders-fill")) return;
    try {
      const matched = matchRegions(regions, currentFeatures.current);
      map.setPaintProperty("borders-fill", "fill-color", colorsExpression.current as mapboxgl.Expression);
      map.setPaintProperty("borders-fill", "fill-opacity", [
        "case",
        ["in", ["get", "name"], ["literal", matched]],
        0.9,
        0.12,
      ] as mapboxgl.Expression);
      if (map.getLayer("borders-label")) {
        map.setPaintProperty("borders-label", "text-opacity", [
          "case",
          ["in", ["get", "name"], ["literal", matched]],
          1,
          0.25,
        ] as mapboxgl.Expression);
      }
      const highlighted = currentFeatures.current.filter((f) => matched.includes(f.properties.name));
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
        const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        map.fitBounds(bounds, { padding: 80, maxZoom: 6, duration: reducedMotion ? 0 : 2500 });
      }
    } catch (e) {
      console.warn("highlight failed", e);
    }
  }

  // Map init
  useEffect(() => {
    const map = new mapboxgl.Map({
      container: mapRef.current!,
      style: "mapbox://styles/mapbox/empty-v9",
      center: [15, 50],
      zoom: 4,
      minZoom: 3,
      maxZoom: 10,
      maxBounds: [[-30, 25], [65, 75]],
      projection: "mercator",
      preserveDrawingBuffer: true,
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
        paint: { "hillshade-intensity": 0.5, "hillshade-shadow-color": "#473B24" } as mapboxgl.HillshadePaint,
      });
      fetch(`${API_URL}/borders/1914`)
        .then((r) => r.json())
        .then((geojson) => {
          const expr = buildColorExpression(geojson.features);
          colorsExpression.current = expr;
          currentFeatures.current = geojson.features;
          map.addSource("borders", { type: "geojson", data: geojson, generateId: true });
          map.addLayer({
            id: "borders-fill",
            type: "fill",
            source: "borders",
            paint: { "fill-color": expr as mapboxgl.Expression, "fill-opacity": 0.85 },
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
          // White overlay on hovered country — additive, doesn't touch fill-opacity logic
          map.addLayer({
            id: "borders-hover",
            type: "fill",
            source: "borders",
            paint: {
              "fill-color": "#ffffff",
              "fill-opacity": [
                "case",
                ["boolean", ["feature-state", "hover"], false],
                0.18,
                0,
              ],
            },
          }, "borders-label");

          let hoveredId: number | null = null;
          map.on("mousemove", "borders-fill", (e) => {
            if (!e.features?.length) return;
            if (hoveredId !== null) {
              map.setFeatureState({ source: "borders", id: hoveredId }, { hover: false });
            }
            hoveredId = (e.features[0] as any).id as number;
            map.setFeatureState({ source: "borders", id: hoveredId }, { hover: true });
            map.getCanvas().style.cursor = "pointer";
          });
          map.on("mouseleave", "borders-fill", () => {
            if (hoveredId !== null) {
              map.setFeatureState({ source: "borders", id: hoveredId }, { hover: false });
            }
            hoveredId = null;
            map.getCanvas().style.cursor = "";
          });

          map.on("click", "borders-fill", async (e) => {
            if (!e.features?.length) return;
            const name = (e.features[0] as any).properties?.name;
            if (!name) return;
            setCountryName(name);
            setCountryCard(null);
            setCountryLoading(true);
            try {
              const res = await fetch(`${API_URL}/country/`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name, year: yearRef.current }),
              });
              setCountryCard(await res.json());
            } finally {
              setCountryLoading(false);
            }
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
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") handleReset(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [result]);

  useEffect(() => { yearRef.current = year; }, [year]);

  useEffect(() => {
    if (!countryName) return;
    const map = mapInstance.current;
    if (!map) return;
    activeRegions.current = [countryName];
    applyHighlight(map, [countryName]);
  }, [countryName]);

  // Year / highlight effect
  useEffect(() => {
    const map = mapInstance.current;
    if (!map || !map.getSource("borders")) return;
    let cancelled = false;
    fetch(`${API_URL}/borders/${year}`)
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
            map.setPaintProperty("borders-fill", "fill-color", colorsExpression.current as mapboxgl.Expression);
            map.setPaintProperty("borders-fill", "fill-opacity", [
              "case",
              ["in", ["get", "name"], ["literal", matched]],
              0.9,
              0.12,
            ] as mapboxgl.Expression);
            if (map.getLayer("borders-label")) {
              map.setPaintProperty("borders-label", "text-opacity", [
                "case",
                ["in", ["get", "name"], ["literal", matched]],
                1,
                0.25,
              ] as mapboxgl.Expression);
            }
          }
        } else if (map.getLayer("borders-fill")) {
          map.setPaintProperty("borders-fill", "fill-color", expr as mapboxgl.Expression);
          map.setPaintProperty("borders-fill", "fill-opacity", 0.85);
          if (map.getLayer("borders-label")) {
            map.setPaintProperty("borders-label", "text-opacity", 1);
          }
        }
      });
    return () => { cancelled = true; };
  }, [year, highlightTrigger]);

  return (
    <div ref={containerRef} style={{ position: "relative", width: "100vw", height: "100vh", backgroundColor: "#0a1628" }}>
      <div
        ref={mapRef}
        style={{
          width: isMobile ? "100%" : (result || loading ? "calc(100% - 380px)" : "100%"),
          height: "100%",
          transition: "width 0.3s",
        }}
        onTransitionEnd={() => mapInstance.current?.resize()}
      />

      {/* Onboarding — only when idle */}
      {!result && !loading && !countryName && (
        <div className="ds-onboarding">
          <h1>Historical Atlas</h1>
          <p>Ask a question below, or click a country on the map</p>
          <div className="ds-example-queries">
            {EXAMPLE_QUERIES.map((q) => (
              <button
                key={q}
                className="ds-example-query"
                onClick={() => { setQuery(q); handleQuery(q); }}
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Query bar */}
      <div
        style={{
          position: "absolute",
          top: 16,
          left: "50%",
          transform: "translateX(-50%)",
          zIndex: 10,
          display: "flex",
          gap: 8,
          width: isMobile ? "calc(100% - 32px)" : "auto",
        }}
      >
        <input
          className="ds-input-query"
          type="text"
          aria-label="Ask about European history"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleQuery()}
          placeholder="Ask about European history..."
          style={isMobile ? { flex: 1, width: "auto" } : undefined}
        />
        <button
          className="ds-btn-primary"
          onClick={() => handleQuery()}
          disabled={loading}
          aria-busy={loading}
        >
          {loading ? "Loading..." : "Ask"}
        </button>
        <div style={{ position: "relative" }}>
          <button
            className="ds-btn-ghost"
            onClick={() => showHistory ? setShowHistory(false) : loadHistory()}
            aria-label="Query history"
          >
            ↑
          </button>
          {showHistory && history.length > 0 && (
            <div style={{
              position: "absolute",
              top: "calc(100% + 6px)",
              right: 0,
              width: 360,
              backgroundColor: "#0f1923",
              border: "1px solid #2a3a4a",
              borderRadius: 4,
              zIndex: 20,
            }}>
              {history.map((h) => (
                <button
                  key={h.id}
                  onClick={() => { setQuery(h.question); setShowHistory(false); handleQuery(h.question); }}
                  style={{
                    display: "block",
                    width: "100%",
                    padding: "10px 14px",
                    background: "none",
                    border: "none",
                    borderBottom: "1px solid #2a3a4a",
                    color: "#c8c0b0",
                    fontSize: 13,
                    textAlign: "left",
                    cursor: "pointer",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "#162432")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
                >
                  {h.question}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Result panel */}
      {(result || loading) && (
        <div
          style={isMobile ? {
            position: "fixed",
            bottom: 0,
            left: 0,
            right: 0,
            height: "60vh",
            width: "100%",
            backgroundColor: "#0f1923",
            color: "#e8e0d0",
            display: "flex",
            flexDirection: "column",
            borderRadius: "12px 12px 0 0",
            borderTop: "1px solid #2a3a4a",
            zIndex: 20,
          } : {
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
          }}
        >
          {/* Drag handle (mobile only) */}
          {isMobile && (
            <div style={{ display: "flex", justifyContent: "center", padding: "10px 0 4px" }}>
              <div style={{ width: 36, height: 4, borderRadius: 2, backgroundColor: "#2a3a4a" }} />
            </div>
          )}
          {/* Scrollable content */}
          <div style={{ flex: 1, overflowY: "auto" }}>
            <div style={{ padding: "20px 20px 0" }}>
              <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
                <button
                  className="ds-btn-ghost"
                  onClick={handleReset}
                  aria-label="Close panel"
                  style={{ padding: "4px 10px", fontSize: 16 }}
                >
                  ×
                </button>
              </div>
              {loading && !result && (
                <p style={{ color: "#6a8a9a", fontStyle: "italic", fontSize: 13 }}>
                  Thinking...
                </p>
              )}
              {error && <p className="ds-error">{error}</p>}
              {displayedAnswer && (
                <p className="ds-answer-text" aria-live="polite">
                  {displayedAnswer}
                </p>
              )}
            </div>

            {result && (
              <>
                <div style={{ margin: "16px 20px 0", padding: "12px 0", borderTop: "1px solid #2a3a4a" }}>
                  <span className="ds-meta-label">{result.year_start} — {result.year_end}</span>
                </div>
                <div style={{ padding: "0 20px" }}>
                  <div style={{ display: "flex", alignItems: "center", marginBottom: 8 }}>
                    <p className="ds-meta-label" style={{ margin: 0 }}>Key Moments</p>
                    {momentIdx >= 0 && (
                      <span style={{ marginLeft: "auto", fontSize: 11, color: "#6a8a9a" }}>
                        {momentIdx + 1} / {result.moments.length}
                      </span>
                    )}
                  </div>
                  {result.moments.map((m, idx) => (
                    <button
                      key={idx}
                      className={[
                        "ds-moment-card",
                        idx === momentIdx ? "ds-moment-active" : "",
                        idx > momentIdx ? "ds-moment-upcoming" : "",
                      ].filter(Boolean).join(" ")}
                      onClick={() => { setMomentIdx(idx); jumpToMoment(m); }}
                      disabled={idx > momentIdx}
                    >
                      <div style={{ fontSize: 12, color: "#e8613c", fontWeight: 600 }}>
                        {m.year} · {m.title}
                      </div>
                      <div style={{ fontSize: 12, color: "#a0a8b0", marginTop: 2, lineHeight: 1.5 }}>
                        {m.description}
                      </div>
                    </button>
                  ))}
                </div>
                <div style={{ padding: "12px 20px 20px", borderTop: "1px solid #2a3a4a", marginTop: 8 }}>
                  <p className="ds-meta-label">Sources</p>
                  {result.citations.map((c, idx) => (
                    <div key={idx} style={{ fontSize: 12, color: "#6a8a9a", marginBottom: 4 }}>
                      · {c}
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>

          {/* Continue — pinned to panel bottom */}
          {result && momentIdx < result.moments.length - 1 && (
            <div style={{ padding: "8px 20px 12px", borderTop: "1px solid #2a3a4a", flexShrink: 0 }}>
              <button
                className="ds-btn-ghost"
                onClick={handleContinue}
                style={{ width: "100%", padding: "8px" }}
              >
                Continue →
              </button>
            </div>
          )}
        </div>
      )}

      {/* Country fact card */}
      {(countryLoading || countryCard) && (
        <div style={{
          position: "absolute",
          ...(isMobile
            ? { top: 130, left: 16, right: 16, width: "auto" }
            : { bottom: 110, left: 20, width: 280 }),
          width: 280,
          backgroundColor: "#0f1923",
          border: "1px solid #2a3a4a",
          borderRadius: 4,
          padding: "14px 16px",
          zIndex: 10,
          color: "#e8e0d0",
        } as React.CSSProperties}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <span className="ds-meta-label" style={{ margin: 0 }}>
              {countryLoading ? countryName : countryCard?.period}
            </span>
            <button
              className="ds-btn-ghost"
              onClick={() => {
                setCountryCard(null);
                setCountryName(null);
                activeRegions.current = null;
                const map = mapInstance.current;
                if (map && map.getLayer("borders-fill")) {
                  map.setPaintProperty("borders-fill", "fill-color", colorsExpression.current as mapboxgl.Expression);
                  map.setPaintProperty("borders-fill", "fill-opacity", 0.85);
                }
                if (map && map.getLayer("borders-label")) {
                  map.setPaintProperty("borders-label", "text-opacity", 1);
                }
              }}
              aria-label="Close"
              style={{ padding: "2px 8px", fontSize: 14 }}
            >×</button>
          </div>
          {countryLoading ? (
            <p style={{ color: "#6a8a9a", fontStyle: "italic", fontSize: 13, margin: 0 }}>Loading...</p>
          ) : countryCard && (
            <>
              <p style={{ fontSize: 12, lineHeight: 1.7, color: "#c8c0b0", margin: "0 0 10px" }}>
                {countryCard.summary}
              </p>
              <ul style={{ listStyle: "none", padding: 0, margin: "0 0 10px" }}>
                {countryCard.key_facts.map((f, i) => (
                  <li key={i} style={{ fontSize: 12, color: "#a0a8b0", marginBottom: 4, paddingLeft: 14, position: "relative" }}>
                    <span style={{ position: "absolute", left: 0, color: "#e8613c" }}>·</span>
                    {f}
                  </li>
                ))}
              </ul>
              {countryCard.citations.length > 0 && (
                <div style={{ borderTop: "1px solid #2a3a4a", paddingTop: 8 }}>
                  <p className="ds-meta-label" style={{ margin: "0 0 4px" }}>Sources</p>
                  {countryCard.citations.map((c, i) => (
                    <div key={i} style={{ fontSize: 11, color: "#6a8a9a", marginBottom: 2 }}>· {c}</div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Export button */}
      <button
        onClick={handleExport}
        disabled={exporting}
        aria-label="Export as PNG"
        style={{
          position: "absolute",
          bottom: isMobile ? 16 : 16,
          right: result || loading ? (isMobile ? 16 : 396) : 16,
          zIndex: 10,
          background: "rgba(15,25,35,0.85)",
          border: "1px solid #2a3a4a",
          borderRadius: 4,
          color: exporting ? "#6a8a9a" : "#c8c0b0",
          fontSize: 18,
          width: 36,
          height: 36,
          cursor: exporting ? "wait" : "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {exporting ? "…" : "⬇"}
      </button>

      {/* Year slider */}
      <div
        style={{
          position: "absolute",
          ...(isMobile
            ? { top: 72, bottom: "auto" }
            : { bottom: 40 }),
          left: "50%",
          transform: "translateX(-50%)",
          zIndex: 10,
          textAlign: "center",
        }}
      >
        <input
          className="ds-year-slider"
          type="range"
          min={0}
          max={YEARS.length - 1}
          value={YEARS.indexOf(year)}
          onChange={(e) => setYear(YEARS[parseInt(e.target.value)])}
          aria-label="Year"
          aria-valuetext={String(year)}
        />
        <div style={{ color: "white", fontSize: 24, marginTop: 4 }}>{year}</div>
      </div>
    </div>
  );
}

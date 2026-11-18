import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import "./App.css";

// All model output and source text is rendered as React text nodes (escaped). No raw HTML anywhere.

const API = import.meta.env.VITE_API_URL ?? "";
const MAP_STYLE = "https://tiles.openfreemap.org/styles/positron";
const EUROPE: [number, number, number, number] = [-11, 34, 48, 63];
const REVEAL_MS = 1000;
const STEPS = ["Searching sources", "Weighing evidence", "Writing answer"];
const STEP_AT_MS = [0, 2500, 5500];

type CaseFeature = { properties: { case: string; name: string }; geometry: { type: string; coordinates: number[][][] } };
type CaseCollection = { type: "FeatureCollection"; features: CaseFeature[] };

type Claim = { claim: string; source: "chunk" | "conversation" | "tool"; chunk_id?: number | null; in_range?: boolean };
type Source = {
  doc_id: string; speaker?: string | null; date?: string | null; source?: string | null; title?: string | null;
  before: string; passage: string; after: string;
};
type ToolCall = { name: string; input: unknown; output: unknown };
type Status = "answered" | "insufficient_evidence" | "needs_clarification" | "error";
type Answer = {
  request_id: string; status: Status; answer: string; message?: string | null; claims: Claim[];
  sources: Source[]; tool_calls: ToolCall[]; case: string | null; code?: string;
};
type Turn = { id: number; question: string; response?: Answer; revealed: boolean };
type DemoConv = { title: string; turns: { question: string; response: Answer }[] };
type Panel = { kind: "chunk"; source: Source; n: number } | { kind: "tool"; calls: ToolCall[] } | { kind: "conversation" };

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const words = (s: string) => new Set(s.toLowerCase().match(/[a-z0-9£$%]+/g) ?? []);

/** Attach each claim to the answer sentence it overlaps most (Hermes UX detail); weak matches go below. */
function placeClaims(answer: string, claims: Claim[]) {
  const sentences = answer.match(/[^.!?]+[.!?]+["')\]]*\s*|[^.!?]+$/g) ?? [answer];
  const marks: Claim[][] = sentences.map(() => []);
  const extra: Claim[] = [];
  for (const c of claims) {
    const cw = words(c.claim);
    let best = -1, score = 0;
    sentences.forEach((s, i) => {
      const sw = words(s);
      const hit = [...cw].filter((w) => sw.has(w)).length / Math.max(1, cw.size);
      if (hit > score) { score = hit; best = i; }
    });
    if (best >= 0 && score >= 0.35) marks[best].push(c); else extra.push(c);
  }
  return { sentences, marks, extra };
}

function useHealth() {
  const [state, setState] = useState<"waking" | "ok" | "down">("waking");
  const [live, setLive] = useState(false);
  useEffect(() => {
    let stop = false, tries = 0;
    const poll = async () => {
      while (!stop) {
        try {
          const r = await fetch(`${API}/api/health`);
          if (r.ok) { const j = await r.json(); setLive(!!j.live); setState("ok"); return; }
        } catch { /* backend asleep or starting */ }
        tries += 1;
        if (tries > 100) { setState("down"); return; }
        await sleep(3000);
      }
    };
    poll();
    return () => { stop = true; };
  }, []);
  return { state, live };
}

function CaseMap({ caseId }: { caseId: string | null }) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const geo = useRef<CaseCollection | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!el.current) return;
    const m = new maplibregl.Map({ container: el.current, style: MAP_STYLE, bounds: EUROPE, attributionControl: { compact: true } });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.current = m;
    m.on("load", async () => {
      const r = await fetch(`${API}/api/cases`);
      geo.current = await r.json();
      m.addSource("cases", { type: "geojson", data: geo.current as unknown as maplibregl.GeoJSONSourceSpecification["data"] });
      m.addLayer({ id: "case-fill", type: "fill", source: "cases",
        paint: { "fill-color": ["case", ["==", ["get", "case"], ""], "#b4532a", "#5b6b7a"], "fill-opacity": 0.18 } });
      m.addLayer({ id: "case-line", type: "line", source: "cases",
        paint: { "line-color": "#5b6b7a", "line-width": 1.2 } });
      m.addLayer({ id: "case-label", type: "symbol", source: "cases",
        layout: { "text-field": ["get", "name"], "text-size": 12, "text-font": ["Noto Sans Regular"], "text-offset": [0, 1.6] },
        paint: { "text-color": "#3a4550", "text-halo-color": "#fff", "text-halo-width": 1.2 } });
      setLoaded(true);
    });
    return () => m.remove();
  }, []);

  useEffect(() => {
    const m = map.current;
    if (!m || !loaded) return;
    const id = caseId ?? "";
    m.setPaintProperty("case-fill", "fill-color", ["case", ["==", ["get", "case"], id], "#b4532a", "#5b6b7a"]);
    m.setPaintProperty("case-fill", "fill-opacity", ["case", ["==", ["get", "case"], id], 0.38, 0.14]);
    m.setPaintProperty("case-line", "line-color", ["case", ["==", ["get", "case"], id], "#8a3a1a", "#5b6b7a"]);
    m.setPaintProperty("case-line", "line-width", ["case", ["==", ["get", "case"], id], 2.4, 1]);
    const f = geo.current?.features.find((x: CaseFeature) => x.properties.case === caseId);
    if (f && f.geometry.type === "Polygon") {
      const b = new maplibregl.LngLatBounds();
      f.geometry.coordinates[0].forEach((p: number[]) => b.extend(p as [number, number]));
      m.fitBounds(b, { padding: 120, maxZoom: 6, duration: 1200 });
    } else {
      m.fitBounds(EUROPE, { padding: 20, duration: 1200 });
    }
  }, [caseId, loaded]);

  return <div ref={el} className="map" data-case={caseId ?? "none"} />;
}

function Marker({ c, n, onOpen }: { c: Claim; n: number | null; onOpen: () => void }) {
  if (c.source === "tool") return <button className="fn fn-tool" onClick={onOpen}>calc</button>;
  if (c.source === "conversation") return <button className="fn fn-conv" onClick={onOpen}>earlier</button>;
  if (n === null) return <span className="fn fn-bad" title="Citation outside the retrieved sources">?</span>;
  return <button className="fn" onClick={onOpen}>{n}</button>;
}

function AnswerView({ r, revealed, onPanel }: { r: Answer; revealed: boolean; onPanel: (p: Panel) => void }) {
  const [shown, setShown] = useState(revealed ? r.answer.length : 0);
  useEffect(() => {
    if (revealed) return;
    const t0 = performance.now();
    let raf = 0;
    const tick = (t: number) => {
      const k = Math.min(1, (t - t0) / REVEAL_MS);
      setShown(Math.round(r.answer.length * k));
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [r.answer, revealed]);
  const done = shown >= r.answer.length;
  const placed = useMemo(() => placeClaims(r.answer, r.claims), [r.answer, r.claims]);

  const open = (c: Claim) => {
    if (c.source === "tool") onPanel({ kind: "tool", calls: r.tool_calls });
    else if (c.source === "conversation") onPanel({ kind: "conversation" });
    else if (c.chunk_id && c.in_range && r.sources[c.chunk_id - 1]) onPanel({ kind: "chunk", source: r.sources[c.chunk_id - 1], n: c.chunk_id });
  };
  const num = (c: Claim) => (c.source === "chunk" && c.in_range && c.chunk_id && r.sources[c.chunk_id - 1] ? c.chunk_id : null);
  const markers = (cs: Claim[]) => cs
    .filter((c, i) => cs.findIndex((d) => d.source === c.source && (c.source !== "chunk" || d.chunk_id === c.chunk_id)) === i)
    .map((c, i) => <Marker key={i} c={c} n={num(c)} onOpen={() => open(c)} />);

  if (r.status === "error") {
    return (
      <div className="answer answer-error">
        <p>{r.message ?? "Sorry, something went wrong."}</p>
        <RequestId id={r.request_id} />
      </div>
    );
  }
  return (
    <div className={`answer answer-${r.status}`}>
      {r.status === "insufficient_evidence" && <div className="badge">Not enough evidence in the sources</div>}
      {r.status === "needs_clarification" && <div className="badge badge-q">Clarifying question</div>}
      {!done ? (
        <p className="typing">{r.answer.slice(0, shown)}</p>
      ) : (
        <>
          <p>
            {placed.sentences.map((s, i) => (
              <span key={i}>{s.trimEnd()}{markers(placed.marks[i])}{" "}</span>
            ))}
          </p>
          {placed.extra.length > 0 && (
            <ul className="extra-claims">
              {placed.extra.map((c, i) => <li key={i}>{c.claim}<Marker c={c} n={num(c)} onOpen={() => open(c)} /></li>)}
            </ul>
          )}
        </>
      )}
      <RequestId id={r.request_id} />
    </div>
  );
}

function RequestId({ id }: { id: string }) {
  return <div className="rid" title="Request id">{id}</div>;
}

function Progress() {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const t0 = performance.now();
    const h = setInterval(() => {
      const el = performance.now() - t0;
      setStep(STEP_AT_MS.filter((ms) => el >= ms).length - 1);
    }, 200);
    return () => clearInterval(h);
  }, []);
  return (
    <ol className="progress">
      {STEPS.map((s, i) => (
        <li key={s} className={i < step ? "done" : i === step ? "active" : ""}>{s}</li>
      ))}
    </ol>
  );
}

function SidePanel({ p, onClose }: { p: Panel; onClose: () => void }) {
  return (
    <aside className="panel">
      <button className="close" onClick={onClose} aria-label="Close">×</button>
      {p.kind === "chunk" && (
        <>
          <div className="panel-n">[{p.n}]</div>
          <dl className="meta">
            {p.source.speaker && (<><dt>Speaker</dt><dd>{p.source.speaker}</dd></>)}
            {p.source.date && (<><dt>Date</dt><dd>{p.source.date}</dd></>)}
            {p.source.source && (<><dt>Source</dt><dd>{p.source.source}</dd></>)}
            {p.source.title && (<><dt>Title</dt><dd>{p.source.title}</dd></>)}
            <dt>Doc id</dt><dd className="mono">{p.source.doc_id}</dd>
          </dl>
          <div className="passage">
            <span className="ctx">{p.source.before}</span>
            <mark>{p.source.passage}</mark>
            <span className="ctx">{p.source.after}</span>
          </div>
        </>
      )}
      {p.kind === "tool" && (
        <>
          <div className="panel-n">calc</div>
          {p.calls.map((c, i) => (
            <div key={i} className="tool">
              <div className="mono">{c.name}</div>
              <div className="lbl">Input</div>
              <pre>{JSON.stringify(c.input, null, 1)}</pre>
              <div className="lbl">Output</div>
              <pre>{JSON.stringify(c.output, null, 1)}</pre>
            </div>
          ))}
        </>
      )}
      {p.kind === "conversation" && (
        <>
          <div className="panel-n">earlier</div>
          <p>Based on an earlier turn in this conversation.</p>
        </>
      )}
    </aside>
  );
}

export default function App() {
  const health = useHealth();
  const [code, setCode] = useState(() => localStorage.getItem("invite") ?? "");
  const [codeDraft, setCodeDraft] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [demo, setDemo] = useState<DemoConv[]>([]);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [input, setInput] = useState("");
  const [panel, setPanel] = useState<Panel | null>(null);
  const [caseId, setCaseId] = useState<string | null>(null);
  const nextId = useRef(1);
  const playToken = useRef(0);
  const endRef = useRef<HTMLDivElement>(null);
  const liveMode = !!code && health.live;

  useEffect(() => {
    if (health.state !== "ok") return;
    fetch(`${API}/api/demo`).then((r) => r.json()).then((j) => {
      const convs: DemoConv[] = j.conversations ?? [];
      setDemo(convs);
      // Deep link (Hermes UX detail): ?demo=N shows example N already revealed; &source=K opens footnote K.
      const qs = new URLSearchParams(location.search);
      const conv = convs[Number(qs.get("demo") ?? -1)];
      if (!conv) return;
      setTurns(conv.turns.map((t) => ({ id: nextId.current++, question: t.question, response: t.response, revealed: true })));
      const last = conv.turns[conv.turns.length - 1].response;
      setCaseId(last.case ?? null);
      const k = Number(qs.get("source") ?? 0);
      if (k && last.sources[k - 1]) setPanel({ kind: "chunk", source: last.sources[k - 1], n: k });
      else if (qs.get("source") === "calc") setPanel({ kind: "tool", calls: last.tool_calls });
    }).catch(() => setDemo([]));
  }, [health.state]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [turns, busy]);

  const push = (question: string) => {
    const id = nextId.current++;
    setTurns((t) => [...t, { id, question, revealed: false }]);
    return id;
  };
  const settle = (id: number, response: Answer) => {
    setTurns((t) => t.map((x) => (x.id === id ? { ...x, response } : x)));
    setCaseId(response.case ?? null);
  };

  const reset = () => { playToken.current++; setTurns([]); setPanel(null); setCaseId(null); setBusy(false); };

  const playDemo = useCallback(async (conv: DemoConv) => {
    const token = ++playToken.current;
    setTurns([]); setPanel(null); setCaseId(null);
    for (const t of conv.turns) {
      if (token !== playToken.current) return;
      setBusy(true);
      const id = push(t.question);
      await sleep(STEP_AT_MS[2] / 2.5);
      if (token !== playToken.current) return;
      setBusy(false);
      settle(id, t.response);
      await sleep(REVEAL_MS + 2200);
    }
  }, []);

  const ask = async () => {
    const q = input.trim();
    if (!q || busy || !liveMode) return;
    setInput(""); setPanel(null);
    const history = turns.filter((t) => t.response).flatMap((t) => [
      { role: "user", content: t.question },
      { role: "assistant", content: t.response!.answer || t.response!.message || "" },
    ]);
    const id = push(q);
    setBusy(true);
    try {
      const r = await fetch(`${API}/api/ask`, {
        method: "POST", headers: { "Content-Type": "application/json", "X-Invite-Code": code },
        body: JSON.stringify({ question: q, history }),
      });
      const j = await r.json();
      if (!r.ok) {
        if (r.status === 401) { localStorage.removeItem("invite"); setCode(""); }
        if (j.code === "daily_cap") setCode("");
        if (r.status === 401 || j.code === "daily_cap") setNotice(j.message);
        settle(id, { request_id: j.request_id ?? "", status: "error", answer: "", message: j.message, claims: [], sources: [], tool_calls: [], case: null });
      } else {
        settle(id, j as Answer);
      }
    } catch {
      settle(id, { request_id: "", status: "error", answer: "", message: "The service could not be reached.", claims: [], sources: [], tool_calls: [], case: null });
    } finally {
      setBusy(false);
    }
  };

  const saveCode = () => {
    const c = codeDraft.trim();
    if (!c) return;
    localStorage.setItem("invite", c); setCode(c); setCodeDraft(""); setNotice(null); reset();
  };
  const leaveLive = () => { localStorage.removeItem("invite"); setCode(""); reset(); };

  return (
    <div className="app">
      <header className="top">
        <div className="brand">Historical Atlas</div>
        <div className="mode">
          {liveMode ? (
            <>
              <span className="pill pill-live">Live</span>
              <button className="link" onClick={leaveLive}>Leave live mode</button>
            </>
          ) : (
            <>
              <span className="pill">Demo</span>
              {health.live && (
                <form onSubmit={(e) => { e.preventDefault(); saveCode(); }} className="code-form">
                  <input type="password" placeholder="Invite code" value={codeDraft} onChange={(e) => setCodeDraft(e.target.value)} autoComplete="off" />
                  <button type="submit">Go live</button>
                </form>
              )}
            </>
          )}
        </div>
      </header>
      <main className="body">
        <section className="chat">
          {health.state !== "ok" ? (
            <div className="waking">
              <div className="spinner" />
              <div>{health.state === "waking" ? "Waking up the server…" : "The server is not responding."}</div>
            </div>
          ) : (
            <>
              {notice && <div className="notice">{notice}</div>}
              {!liveMode && (
                <div className="examples">
                  {demo.map((c) => (
                    <button key={c.title} className="example" onClick={() => playDemo(c)}>{c.title}</button>
                  ))}
                </div>
              )}
              <div className="turns">
                {turns.map((t) => (
                  <div key={t.id} className="turn">
                    <div className="q">{t.question}</div>
                    {t.response ? (
                      <AnswerView r={t.response} revealed={t.revealed} onPanel={setPanel} />
                    ) : (
                      <Progress />
                    )}
                  </div>
                ))}
                <div ref={endRef} />
              </div>
              {liveMode && (
                <form className="ask" onSubmit={(e) => { e.preventDefault(); ask(); }}>
                  <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask about the five interwar disputes" disabled={busy} maxLength={1000} />
                  <button type="submit" disabled={busy || !input.trim()}>Ask</button>
                  {turns.length > 0 && <button type="button" className="link" onClick={reset}>New conversation</button>}
                </form>
              )}
            </>
          )}
        </section>
        <section className="mapwrap">
          <CaseMap caseId={caseId} />
          {panel && <SidePanel p={panel} onClose={() => setPanel(null)} />}
        </section>
      </main>
    </div>
  );
}

import { lazy, Suspense, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { analyze, searchRegions } from "./api";
import type { Analysis, Region } from "./types";
const Results = lazy(() => import("./components/Results"));
const MapPicker = lazy(() => import("./components/MapPicker"));
export default function App() {
  const [query, setQuery] = useState("");
  const [regions, setRegions] = useState<Region[]>([]);
  const [searchState, setSearchState] = useState("");
  const [latitude, setLatitude] = useState("17.385");
  const [longitude, setLongitude] = useState("78.4867");
  const [start, setStart] = useState("1990");
  const [end, setEnd] = useState(String(new Date().getUTCFullYear() - 1));
  const [selected, setSelected] = useState<Region | null>(null);
  const [result, setResult] = useState<Analysis | null>(null);
  const [resultLabel, setResultLabel] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showSearch, setShowSearch] = useState(false);
  const analysisController = useRef<AbortController | null>(null);
  const maxYear = new Date().getUTCFullYear() - 1;
  useEffect(() => () => analysisController.current?.abort(), []);
  useEffect(() => {
    const controller = new AbortController();
    setRegions([]);
    if (!showSearch || query.trim().length < 2) {
      setSearchState("");
      return;
    }
    setSearchState("Searching...");
    const timer = setTimeout(async () => {
      try {
        const data = await searchRegions(query.trim(), controller.signal);
        if (!controller.signal.aborted) {
          setRegions(data.results);
          setSearchState(
            data.results.length
              ? ""
              : "No cities found. Enter coordinates instead.",
          );
        }
      } catch (e) {
        if (!controller.signal.aborted)
          setSearchState(
            e instanceof Error ? e.message : "City search failed.",
          );
      }
    }, 400);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, showSearch]);
  function choose(region: Region) {
    setSelected(region);
    setQuery(
      [region.name, region.admin1, region.country].filter(Boolean).join(", "),
    );
    setLatitude(String(region.latitude));
    setLongitude(String(region.longitude));
    setShowSearch(false);
    setRegions([]);
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (Number(start) > Number(end) || Number(end) - Number(start) + 1 > 60) {
      setError("Choose an ordered range of at most 60 years.");
      return;
    }
    analysisController.current?.abort();
    const controller = new AbortController();
    analysisController.current = controller;
    setLoading(true);
    setResult(null);
    const label =
      selected &&
      selected.latitude === Number(latitude) &&
      selected.longitude === Number(longitude)
        ? selected.name
        : `${Number(latitude).toFixed(4)}, ${Number(longitude).toFixed(4)}`;
    const timeout = setTimeout(() => controller.abort(), 250000);
    try {
      const data = await analyze(
        {
          latitude: Number(latitude),
          longitude: Number(longitude),
          start_year: Number(start),
          end_year: Number(end),
          hazard: "heatwave",
        },
        controller.signal,
      );
      setResult(data);
      setResultLabel(label);
    } catch (e) {
      setError(
        controller.signal.aborted
          ? "Analysis cancelled or timed out. Completed downloads remain cached; you can retry."
          : e instanceof Error
            ? e.message
            : "Analysis failed. Please try again.",
      );
    } finally {
      clearTimeout(timeout);
      setLoading(false);
    }
  }
  return (
    <>
      <header className="site-header">
        <a href="#main" className="brand">
          <span className="brand-mark" aria-hidden="true">
            C
          </span>
          <span>CLIMATE / OBSERVATORY</span>
        </a>
        <span className="header-note">Historical hazard intelligence</span>
      </header>
      <main id="main">
        <section className="hero">
          <div>
            <p className="eyebrow">PAST WEATHER. CLEARER PERSPECTIVE.</p>
            <h1>
              Climate Hazard
              <br />
              <span>Trend Analyzer</span>
            </h1>
            <p className="hero-copy">
              Explore how heatwaves have changed where you live.
              <br />
              Historical evidence, consistent thresholds, transparent methods.
            </p>
          </div>
          <div className="hero-tag">
            <span className="status-dot" /> HEATWAVE ANALYSIS{" "}
            <small>Daily maxima / ERA5 reanalysis</small>
          </div>
        </section>
        <section className="panel controls" aria-label="Analysis controls">
          <form onSubmit={submit}>
            <fieldset disabled={loading}>
              <legend className="sr-only">
                Select location and historical years
              </legend>
              <div className="control-heading">
                <div>
                  <p className="eyebrow">01 / DEFINE YOUR ANALYSIS</p>
                  <h2>A place. A period. A clearer picture.</h2>
                </div>
                <span className="badge">Baseline: 1991-2020</span>
              </div>
              <div className="control-grid">
                <div className="search-field">
                  <label htmlFor="city">Find a city</label>
                  <input
                    id="city"
                    type="search"
                    value={query}
                    onChange={(e) => {
                      setQuery(e.target.value);
                      setSelected(null);
                      setShowSearch(true);
                    }}
                    placeholder="Search Hyderabad, Madrid..."
                    autoComplete="off"
                    aria-describedby="search-status"
                  />
                  {showSearch && regions.length > 0 && (
                    <ul
                      className="search-results"
                      aria-label="City search results"
                    >
                      {regions.map((r, i) => (
                        <li key={i}>
                          <button type="button" onClick={() => choose(r)}>
                            {r.name}
                            <small>
                              {[r.admin1, r.country].filter(Boolean).join(", ")}
                            </small>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                  <small id="search-status" role="status">
                    {searchState ||
                      "Select a city result or enter coordinates below."}
                  </small>
                </div>
                <div>
                  <label htmlFor="hazard">Hazard</label>
                  <select id="hazard" defaultValue="heatwave">
                    <option value="heatwave">Heatwave</option>
                  </select>
                  <small>More hazards planned</small>
                </div>
              </div>
              <Suspense
                fallback={<div className="map map-loading">Loading map...</div>}
              >
                <MapPicker
                  latitude={Number(latitude)}
                  longitude={Number(longitude)}
                  grid={
                    result
                      ? {
                          latitude: result.source.grid_latitude,
                          longitude: result.source.grid_longitude,
                        }
                      : null
                  }
                  disabled={loading}
                  onPick={(lat, lon) => {
                    setLatitude(String(lat));
                    setLongitude(String(lon));
                    setSelected(null);
                    setQuery("");
                  }}
                />
              </Suspense>
              <div className="coordinate-grid">
                <div>
                  <label htmlFor="latitude">Latitude</label>
                  <input
                    id="latitude"
                    type="number"
                    min="-90"
                    max="90"
                    step="any"
                    value={latitude}
                    onChange={(e) => setLatitude(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <label htmlFor="longitude">Longitude</label>
                  <input
                    id="longitude"
                    type="number"
                    min="-180"
                    max="180"
                    step="any"
                    value={longitude}
                    onChange={(e) => setLongitude(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <label htmlFor="start">Start year</label>
                  <input
                    id="start"
                    type="number"
                    min="1940"
                    max={maxYear}
                    value={start}
                    onChange={(e) => setStart(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <label htmlFor="end">End year</label>
                  <input
                    id="end"
                    type="number"
                    min="1940"
                    max={maxYear}
                    value={end}
                    onChange={(e) => setEnd(e.target.value)}
                    required
                  />
                </div>
                <button className="primary" type="submit">
                  {loading ? "Analyzing..." : "Analyze heatwaves"}{" "}
                  <span aria-hidden="true">&rarr;</span>
                </button>
              </div>
            </fieldset>
            <div className="control-foot">
              <small>
                Point analysis / completed calendar years / maximum 60 years
              </small>
              {loading && (
                <button
                  type="button"
                  className="text-button"
                  onClick={() => analysisController.current?.abort()}
                >
                  Cancel analysis
                </button>
              )}
            </div>
          </form>
        </section>
        {error && (
          <div className="error" role="alert">
            <strong>Unable to complete analysis.</strong> {error}
          </div>
        )}
        {loading && (
          <div className="loading panel" role="status">
            <span className="spinner" />
            <h2>Reading the historical record</h2>
            <p>
              Fetching uncached weather blocks and calculating the regional
              threshold. First requests can take a few minutes.
            </p>
          </div>
        )}
        {result && (
          <Suspense fallback={<p role="status">Loading charts...</p>}>
            <Results
              key={result.cache.created_at + resultLabel}
              data={result}
              label={resultLabel}
            />
          </Suspense>
        )}
        {!result && !loading && (
          <section className="empty-state">
            <div className="spark" aria-hidden="true">
              <i />
              <i />
              <i />
              <i />
              <i />
              <i />
              <i />
              <i />
            </div>
            <h2>Start with a place you know.</h2>
            <p>
              Choose a city or coordinates and analyze a historical period.
              <br />
              Your results will show frequency, duration, intensity, and data
              coverage.
            </p>
            <div className="empty-facts">
              <span>95th-percentile threshold</span>
              <span>3+ consecutive hot days</span>
              <span>No fabricated observations</span>
            </div>
          </section>
        )}
      </main>
      <footer>
        <span>Climate Hazard Trend Analyzer</span>
        <span>Built for exploration. Interpret with care.</span>
      </footer>
    </>
  );
}

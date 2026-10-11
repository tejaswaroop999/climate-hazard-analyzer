import { useState } from "react";
import type { Analysis } from "../types";
import Charts from "./Charts";
import { downloadCsv } from "../csv";
export default function Results({
  data,
  label,
}: {
  data: Analysis;
  label: string;
}) {
  const [page, setPage] = useState(0);
  const { summary: s, data_quality: q, trend } = data;
  const mk = trend.mann_kendall;
  const pages = Math.ceil(data.events.length / 10);
  const cards = [
    ["Total heatwaves", s.total_events.toLocaleString(), "Events of 3+ days"],
    [
      "Heatwave days",
      s.total_heatwave_days.toLocaleString(),
      "Across the selected period",
    ],
    [
      "Longest event",
      `${s.longest_event_days} days`,
      "Consecutive qualifying days",
    ],
    [
      "Peak temperature",
      `${s.peak_temperature_c.toFixed(1)} °C`,
      "Maximum across all valid days",
    ],
    [
      "Frequency trend",
      mk
        ? `${mk.sen_slope_per_decade >= 0 ? "+" : ""}${mk.sen_slope_per_decade.toFixed(2)} / decade`
        : "Unavailable",
      mk
        ? mk.significant
          ? `Sen's slope; significant (p = ${mk.p_value.toFixed(3)})`
          : `Sen's slope; not significant (p = ${mk.p_value.toFixed(2)})`
        : "Needs 10+ well-covered years",
    ],
  ];
  return (
    <div className="results">
      <div className="results-heading">
        <div>
          <p className="eyebrow">ANALYSIS RESULTS</p>
          <h2>{label}</h2>
          <p>
            {data.period.start_date.slice(0, 4)} -{" "}
            {data.period.end_date.slice(0, 4)} / ERA5 /{" "}
            {data.cache.hit
              ? "From MongoDB cache"
              : "Freshly analyzed & stored"}
          </p>
        </div>
        <button className="secondary" onClick={() => downloadCsv(data)}>
          Export annual CSV
        </button>
      </div>
      <div className="metrics">
        {cards.map(([title, value, subtitle]) => (
          <article className="metric" key={title}>
            <p>{title}</p>
            <strong>{value}</strong>
            <small>{subtitle}</small>
          </article>
        ))}
      </div>
      <section className="insight" aria-label="Summary insight">
        <span className="insight-icon" aria-hidden="true">
          &#8599;
        </span>
        <div>
          <p className="eyebrow">WHAT THE DATA SAYS</p>
          <p>{trend.insight}</p>
        </div>
      </section>
      <Charts rows={data.annual_metrics} />
      <div className="details-grid">
        <section className="panel">
          <p className="eyebrow">TRANSPARENCY</p>
          <h2>Data quality</h2>
          <div className="quality-head">
            <strong>{q.coverage_percentage.toFixed(2)}%</strong>
            <span>valid observations</span>
          </div>
          <meter
            min="0"
            max="100"
            value={q.coverage_percentage}
            aria-label="Valid observation coverage"
          />
          <dl className="quality-list">
            <div>
              <dt>Requested days</dt>
              <dd>{q.requested_days.toLocaleString()}</dd>
            </div>
            <div>
              <dt>Valid / missing</dt>
              <dd>
                {q.valid_days.toLocaleString()} /{" "}
                {q.missing_days.toLocaleString()}
              </dd>
            </div>
            <div>
              <dt>Duplicates / conflicts</dt>
              <dd>
                {q.duplicate_rows} / {q.conflicting_dates}
              </dd>
            </div>
            <div>
              <dt>Rejected temperatures</dt>
              <dd>{q.rejected_temperatures}</dd>
            </div>
            <div>
              <dt>Baseline coverage</dt>
              <dd>
                {data.baseline_data_quality.coverage_percentage.toFixed(2)}%
              </dd>
            </div>
            <div>
              <dt>Interpolated days</dt>
              <dd>{q.interpolated_days}</dd>
            </div>
          </dl>
          <ul className="warnings">
            {q.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </section>
        <section className="panel methodology">
          <p className="eyebrow">THE METHOD</p>
          <h2>A consistent reference point</h2>
          <div className="threshold">
            <strong>{data.threshold.temperature_c.toFixed(2)} °C</strong>
            <span>95th percentile / 1991-2020 baseline</span>
          </div>
          <p>
            A heatwave is at least <b>3 consecutive days</b> with daily maximum
            temperature strictly above this fixed regional threshold. Missing
            days break the sequence; no gaps are interpolated.
          </p>
          <p>
            Frequency counts an event in its start year. Days and intensity are
            assigned to the year they occur. Zero-event years have no intensity
            value.
          </p>
          <p>
            Trends require at least 10 years. Years below 95% coverage are
            excluded. Significance comes from a Mann-Kendall test (p &lt; 0.05)
            with Sen&apos;s slope; the dashed OLS line is a visual guide.
            Percentages are shown only when the trend is significant and the
            early period averages at least one event a year.
          </p>
          <p>
            This pooled annual threshold emphasizes the hottest season. It is a
            screening indicator, not an official health warning or attribution
            study.
          </p>
          <small>
            Point analysis at grid {data.source.grid_latitude},{" "}
            {data.source.grid_longitude}; {data.source.timezone}. Algorithm{" "}
            {data.algorithm_version}.
          </small>
        </section>
      </div>
      <section className="panel">
        <div className="panel-title">
          <div>
            <p className="eyebrow">EVENT RECORD</p>
            <h2>Detected heatwaves</h2>
          </div>
          <span className="badge">{data.events.length} events</span>
        </div>
        <div className="table-scroll">
          <table>
            <caption className="sr-only">
              Heatwave event dates, durations, temperatures and intensities
            </caption>
            <thead>
              <tr>
                <th scope="col">Start</th>
                <th scope="col">End</th>
                <th scope="col">Duration</th>
                <th scope="col">Peak (°C)</th>
                <th scope="col">Mean excess (°C)</th>
              </tr>
            </thead>
            <tbody>
              {data.events.slice(page * 10, page * 10 + 10).map((e) => (
                <tr key={e.start_date}>
                  <td>{e.start_date}</td>
                  <td>{e.end_date}</td>
                  <td>{e.duration_days} days</td>
                  <td>{e.peak_temperature_c.toFixed(1)}</td>
                  <td>+{e.mean_intensity_c.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!data.events.length && (
            <p className="empty-table">
              No heatwaves detected in the valid observations.
            </p>
          )}
        </div>
        {pages > 1 && (
          <div className="pagination">
            <button
              className="secondary"
              disabled={!page}
              onClick={() => setPage(page - 1)}
            >
              Previous
            </button>
            <span>
              Page {page + 1} of {pages}
            </span>
            <button
              className="secondary"
              disabled={page + 1 >= pages}
              onClick={() => setPage(page + 1)}
            >
              Next
            </button>
          </div>
        )}
      </section>
      <details className="panel">
        <summary>Annual data &amp; coverage (accessible chart values)</summary>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Year</th>
                <th scope="col">Events</th>
                <th scope="col">Days</th>
                <th scope="col">Mean excess (°C)</th>
                <th scope="col">Max excess (°C)</th>
                <th scope="col">Mean duration (days)</th>
                <th scope="col">Longest duration (days)</th>
                <th scope="col">5-year event mean</th>
                <th scope="col">Event regression</th>
                <th scope="col">Coverage</th>
                <th scope="col">Trend eligible</th>
              </tr>
            </thead>
            <tbody>
              {data.annual_metrics.map((a) => (
                <tr key={a.year}>
                  <td>{a.year}</td>
                  <td>{a.event_count}</td>
                  <td>{a.heatwave_days}</td>
                  <td>{a.mean_intensity_c?.toFixed(2) ?? "N/A"}</td>
                  <td>{a.max_intensity_c?.toFixed(2) ?? "N/A"}</td>
                  <td>{a.mean_event_duration_days?.toFixed(2) ?? "N/A"}</td>
                  <td>{a.max_event_duration_days ?? "N/A"}</td>
                  <td>{a.rolling_5_year_events?.toFixed(2) ?? "N/A"}</td>
                  <td>{a.regression_events?.toFixed(2) ?? "N/A"}</td>
                  <td>{a.coverage_percentage}%</td>
                  <td>{a.eligible_for_trend ? "Yes" : "No"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <p className="provenance">
        <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">
          Weather data by Open-Meteo
        </a>
        , ERA5 by Copernicus/ECMWF. Reanalysis estimates, not local station
        observations. Stored {new Date(data.cache.created_at).toLocaleString()};
        expires {new Date(data.cache.expires_at).toLocaleDateString()}.
      </p>
    </div>
  );
}

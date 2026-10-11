import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import Results from "./Results";
import type { Analysis } from "../types";

afterEach(cleanup);

const quality = {
  requested_days: 3653,
  valid_days: 3653,
  missing_days: 0,
  coverage_percentage: 100,
  duplicate_rows: 0,
  conflicting_dates: 0,
  rejected_temperatures: 0,
  invalid_dates: 0,
  interpolated_days: 0,
  warnings: [],
};

function analysis(significant: boolean): Analysis {
  return {
    region: { latitude: 17.39, longitude: 78.49, spatial_method: "point" },
    period: { start_date: "2000-01-01", end_date: "2009-12-31" },
    threshold: {
      temperature_c: 39.3,
      baseline_start: "1991-01-01",
      baseline_end: "2020-12-31",
      method: "",
    },
    summary: {
      total_events: 12,
      total_heatwave_days: 50,
      longest_event_days: 9,
      peak_temperature_c: 43.1,
    },
    annual_metrics: [],
    events: [],
    trend: {
      method: "",
      insight: "Heatwaves averaged 1.2 events/year in 2000-2004 and 0.4 in 2005-2009.",
      regression: { slope_events_per_decade: -1.1, r_squared: 0.1, years_used: 10 },
      comparison: null,
      mann_kendall: {
        p_value: significant ? 0.012 : 0.5,
        significant,
        direction: significant ? "decreasing" : "no significant trend",
        sen_slope_per_decade: -0.5,
        years_used: 10,
      },
    },
    data_quality: quality,
    baseline_data_quality: quality,
    cache: {
      hit: true,
      created_at: "2026-10-11T00:00:00Z",
      expires_at: "2026-11-10T00:00:00Z",
    },
    source: {
      provider: "Open-Meteo",
      model: "era5",
      timezone: "Asia/Kolkata",
      grid_latitude: 17.375,
      grid_longitude: 78.5,
      attribution: "",
    },
    algorithm_version: "heatwave-1.1.0",
  };
}

it("labels a non-significant trend instead of implying change", () => {
  render(<Results data={analysis(false)} label="Hyderabad" />);
  expect(screen.getByText(/not significant \(p = 0.50\)/)).toBeInTheDocument();
  expect(screen.getByText(/1.2 events\/year/)).toBeInTheDocument();
  expect(screen.getByText("No heatwaves detected in the valid observations.")).toBeInTheDocument();
});

it("reports significance with the p-value", () => {
  render(<Results data={analysis(true)} label="Hyderabad" />);
  expect(screen.getByText(/significant \(p = 0.012\)/)).toBeInTheDocument();
  expect(screen.getByText("-0.50 / decade")).toBeInTheDocument();
});

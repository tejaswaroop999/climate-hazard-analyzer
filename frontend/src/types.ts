export interface Region {
  name: string;
  latitude: number;
  longitude: number;
  admin1: string;
  country: string;
}
export interface AnalysisInput {
  latitude: number;
  longitude: number;
  start_year: number;
  end_year: number;
  hazard: "heatwave";
}
export interface AnnualMetric {
  mean_event_duration_days: number | null;
  max_event_duration_days: number | null;
  year: number;
  event_count: number;
  heatwave_days: number;
  mean_intensity_c: number | null;
  max_intensity_c: number | null;
  rolling_5_year_events: number | null;
  regression_events: number | null;
  coverage_percentage: number;
  complete_calendar_year: boolean;
  eligible_for_trend: boolean;
}
export interface HeatwaveEvent {
  start_date: string;
  end_date: string;
  duration_days: number;
  peak_temperature_c: number;
  mean_intensity_c: number;
  max_intensity_c: number;
}
export interface Quality {
  requested_days: number;
  valid_days: number;
  missing_days: number;
  coverage_percentage: number;
  duplicate_rows: number;
  conflicting_dates: number;
  rejected_temperatures: number;
  invalid_dates: number;
  interpolated_days: number;
  warnings: string[];
}
export interface Analysis {
  region: { latitude: number; longitude: number; spatial_method: string };
  period: { start_date: string; end_date: string };
  threshold: {
    temperature_c: number;
    baseline_start: string;
    baseline_end: string;
    method: string;
  };
  summary: {
    total_events: number;
    total_heatwave_days: number;
    longest_event_days: number;
    peak_temperature_c: number;
  };
  annual_metrics: AnnualMetric[];
  events: HeatwaveEvent[];
  trend: {
    method: string;
    insight: string;
    regression: {
      slope_events_per_decade: number;
      r_squared: number | null;
      years_used: number;
    } | null;
    comparison: {
      first_window: [number, number];
      last_window: [number, number];
      first_mean: number;
      last_mean: number;
      absolute_change: number;
      percent_change: number | null;
    } | null;
    mann_kendall: {
      p_value: number;
      significant: boolean;
      direction: string;
      sen_slope_per_decade: number;
      years_used: number;
    } | null;
  };
  data_quality: Quality;
  baseline_data_quality: Quality;
  cache: { hit: boolean; created_at: string; expires_at: string };
  source: {
    provider: string;
    model: string;
    timezone: string;
    grid_latitude: number;
    grid_longitude: number;
    attribution: string;
  };
  algorithm_version: string;
}

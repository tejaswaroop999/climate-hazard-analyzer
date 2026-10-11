import type { Analysis } from "./types";
export function csvCell(value: unknown): string {
  let text = value == null ? "" : String(value);
  if (/^[=+@-]/.test(text) && typeof value !== "number") text = `'${text}`;
  return `"${text.replaceAll('"', '""')}"`;
}
export function annualCsv(data: Analysis): string {
  const header = [
    "year",
    "event_count",
    "heatwave_days",
    "mean_event_duration_days",
    "max_event_duration_days",
    "mean_intensity_c",
    "max_intensity_c",
    "coverage_percentage",
    "eligible_for_trend",
    "rolling_5_year_events",
    "threshold_c",
    "baseline",
    "latitude",
    "longitude",
    "algorithm",
  ];
  const rows = data.annual_metrics.map((a) => [
    a.year,
    a.event_count,
    a.heatwave_days,
    a.mean_event_duration_days,
    a.max_event_duration_days,
    a.mean_intensity_c,
    a.max_intensity_c,
    a.coverage_percentage,
    a.eligible_for_trend,
    a.rolling_5_year_events,
    data.threshold.temperature_c,
    "1991-2020",
    data.region.latitude,
    data.region.longitude,
    data.algorithm_version,
  ]);
  return [header, ...rows]
    .map((row) => row.map(csvCell).join(","))
    .join("\r\n");
}
export function downloadCsv(data: Analysis) {
  const url = URL.createObjectURL(
    new Blob([annualCsv(data)], { type: "text/csv;charset=utf-8" }),
  );
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "heatwave-annual-metrics.csv";
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

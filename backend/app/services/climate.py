"""Pure, deterministic climate calculations; all temperatures are Celsius."""

from collections import defaultdict
from datetime import date, timedelta
from math import isfinite
import numpy as np

ALGORITHM_VERSION = "heatwave-1.0.0"
BASELINE_START = date(1991, 1, 1)
BASELINE_END = date(2020, 12, 31)
MIN_COVERAGE = 0.95


class DataQualityError(ValueError):
    pass


def dates_between(start, end):
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def normalize(records, start, end):
    """Conflicting duplicate dates are unknown, never cherry-picked or averaged."""
    grouped = defaultdict(list)
    invalid_dates = 0
    outside = 0
    rejected = 0
    for raw_day, raw_value in records:
        try:
            day = date.fromisoformat(raw_day)
        except (ValueError, TypeError):
            invalid_dates += 1
            continue
        if not start <= day <= end:
            outside += 1
            continue
        value = None
        if isinstance(raw_value, (float, int)) and not isinstance(raw_value, bool):
            if isfinite(raw_value) and -90 <= raw_value <= 65:
                value = float(raw_value)
            else:
                rejected += 1
        elif raw_value is not None:
            rejected += 1
        grouped[day].append(value)
    duplicate_rows = sum(len(values) - 1 for values in grouped.values())
    conflicts = sum(len(set(values)) > 1 for values in grouped.values())
    daily = {
        day: (
            grouped[day][0] if day in grouped and len(set(grouped[day])) == 1 else None
        )
        for day in dates_between(start, end)
    }
    valid = sum(v is not None for v in daily.values())
    quality = {
        "requested_days": len(daily),
        "valid_days": valid,
        "missing_days": len(daily) - valid,
        "coverage_percentage": round(100 * valid / len(daily), 2),
        "duplicate_rows": duplicate_rows,
        "conflicting_dates": conflicts,
        "invalid_dates": invalid_dates,
        "out_of_range_dates": outside,
        "rejected_temperatures": rejected,
        "interpolated_days": 0,
        "warnings": [],
    }
    if valid < len(daily):
        quality["warnings"].append(
            "Missing or rejected observations break events; counts may be underestimated."
        )
    if duplicate_rows:
        quality["warnings"].append(
            "Duplicate dates collapsed; conflicting values treated as missing."
        )
    if rejected:
        quality["warnings"].append(
            "Non-numeric or physically implausible temperatures rejected (-90 to 65 C)."
        )
    if invalid_dates or outside:
        quality["warnings"].append("Malformed or out-of-period dates ignored.")
    return daily, quality


def baseline_threshold(records):
    daily, quality = normalize(records, BASELINE_START, BASELINE_END)
    # Require each baseline year to be represented, not merely a large pooled sample.
    for year in range(1991, 2021):
        values = [v for d, v in daily.items() if d.year == year]
        if sum(v is not None for v in values) / len(values) < MIN_COVERAGE:
            raise DataQualityError(f"Baseline year {year} has less than 95% coverage")
    threshold = float(
        np.percentile([v for v in daily.values() if v is not None], 95, method="linear")
    )
    return threshold, quality


def detect_events(daily, threshold):
    events = []
    run = []

    def flush():
        if len(run) >= 3:
            values = [v for _, v in run]
            events.append(
                {
                    "start_date": run[0][0].isoformat(),
                    "end_date": run[-1][0].isoformat(),
                    "duration_days": len(run),
                    "peak_temperature_c": max(values),
                    "mean_intensity_c": float(np.mean(values)) - threshold,
                    "max_intensity_c": max(values) - threshold,
                }
            )
        run.clear()

    previous = None
    for day, value in sorted(daily.items()):
        # Date adjacency is checked even if a caller provides a sparse series.
        if previous is not None and day != previous + timedelta(days=1):
            flush()
        if value is not None and value > threshold:
            run.append((day, value))
        else:
            flush()
        previous = day
    flush()
    return events


def regression_slope(rows, metric):
    points = [
        (r["year"], r[metric])
        for r in rows
        if r["eligible_for_trend"] and r.get(metric) is not None
    ]
    if len(points) < 10:
        return None
    x, y = np.array(points, dtype=float).T
    centered = x - x.mean()
    return float(np.dot(centered, y - y.mean()) / np.dot(centered, centered)) * 10


def calculate_trend(annual):
    eligible = [a for a in annual if a["eligible_for_trend"]]
    regression = None
    if len(eligible) >= 10:
        x = np.array([a["year"] for a in eligible], dtype=float)
        y = np.array([a["event_count"] for a in eligible], dtype=float)
        centered = x - x.mean()
        slope = float(np.dot(centered, y - y.mean()) / np.dot(centered, centered))
        intercept = float(y.mean() - slope * x.mean())
        residual = float(np.sum((y - (slope * x + intercept)) ** 2))
        total = float(np.sum((y - y.mean()) ** 2))
        regression = {
            "slope_events_per_decade": slope * 10,
            "intercept": intercept,
            "r_squared": 1 - residual / total if total > 0 else None,
            "years_used": len(eligible),
        }
    comparison = None
    # Fixed, non-overlapping endpoint windows; no substitution of convenient years.
    if len(annual) >= 10 and all(
        a["eligible_for_trend"] for a in annual[:5] + annual[-5:]
    ):
        first, last = annual[:5], annual[-5:]
        before = float(np.mean([a["event_count"] for a in first]))
        after = float(np.mean([a["event_count"] for a in last]))
        comparison = {
            "first_window": [first[0]["year"], first[-1]["year"]],
            "last_window": [last[0]["year"], last[-1]["year"]],
            "first_mean": before,
            "last_mean": after,
            "absolute_change": after - before,
            "percent_change": (after - before) / before * 100 if before > 0 else None,
        }
    for i, row in enumerate(annual):
        window = annual[max(0, i - 4) : i + 1]
        row["rolling_5_year_events"] = (
            float(np.mean([a["event_count"] for a in window]))
            if len(window) == 5 and all(a["eligible_for_trend"] for a in window)
            else None
        )
        row["regression_events"] = (
            regression["slope_events_per_decade"] / 10 * row["year"]
            + regression["intercept"]
            if regression
            else None
        )
    insight = "Insufficient well-covered years for a ten-year trend comparison."
    if comparison:
        change = comparison["percent_change"]
        windows = f"{comparison['first_window'][0]}-{comparison['first_window'][1]} versus {comparison['last_window'][0]}-{comparison['last_window'][1]}"
        if change is None:
            insight = f"Mean annual events changed from 0 to {comparison['last_mean']:.1f} ({windows}); percentage change is undefined."
        else:
            direction = (
                "increased" if change > 0 else "decreased" if change < 0 else "changed"
            )
            insight = f"Mean annual heatwave events {direction} by {abs(change):.1f}% ({windows}, five-year means). This is descriptive, not proof of causation or statistical significance."
    elif regression:
        insight = f"Linear regression estimates {regression['slope_events_per_decade']:+.2f} events per decade across {regression['years_used']} well-covered years. This is descriptive, without a significance claim."
    return {
        "method": "five-year endpoint means; ordinary least squares; trailing five-year mean",
        "comparison": comparison,
        "regression": regression,
        "insight": insight,
        "duration_slope_days_per_decade": regression_slope(
            annual, "mean_event_duration_days"
        ),
        "heatwave_days_slope_per_decade": regression_slope(annual, "heatwave_days"),
    }


def analyze(records, baseline_records, start, end):
    threshold, baseline_quality = baseline_threshold(baseline_records)
    daily, quality = normalize(records, start, end)
    if quality["valid_days"] == 0:
        raise DataQualityError("No valid observations in the selected period")
    events = detect_events(daily, threshold)
    event_days = {}
    starts = defaultdict(int)
    durations = defaultdict(list)
    for event in events:
        first, last = (
            date.fromisoformat(event["start_date"]),
            date.fromisoformat(event["end_date"]),
        )
        starts[first.year] += 1
        durations[first.year].append(event["duration_days"])
        for day in dates_between(first, last):
            event_days[day] = daily[day] - threshold
    annual = []
    for year in range(start.year, end.year + 1):
        year_days = [v for d, v in daily.items() if d.year == year]
        expected = (date(year + 1, 1, 1) - date(year, 1, 1)).days
        valid = sum(v is not None for v in year_days)
        intensities = [v for d, v in event_days.items() if d.year == year]
        full = len(year_days) == expected
        annual.append(
            {
                "year": year,
                "event_count": starts[year],
                "heatwave_days": len(intensities),
                "mean_event_duration_days": float(np.mean(durations[year]))
                if durations[year]
                else None,
                "max_event_duration_days": max(durations[year])
                if durations[year]
                else None,
                "mean_intensity_c": float(np.mean(intensities))
                if intensities
                else None,
                "max_intensity_c": max(intensities) if intensities else None,
                "coverage_percentage": round(100 * valid / expected, 2),
                "complete_calendar_year": full,
                "eligible_for_trend": full and valid / expected >= MIN_COVERAGE,
            }
        )
    if any(not a["eligible_for_trend"] for a in annual):
        quality["warnings"].append(
            "Partial years or years below 95% coverage excluded from trends; observed counts remain visible."
        )
    quality["warnings"].append(
        "Events touching the selected period boundary may be truncated; no observations beyond the period are inferred."
    )
    if baseline_quality["missing_days"]:
        quality["warnings"].append(
            "Baseline contains missing data; each baseline year still passes the 95% coverage minimum."
        )
    trend = calculate_trend(annual)
    return {
        "period": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        "threshold": {
            "temperature_c": threshold,
            "percentile": 95,
            "baseline_start": BASELINE_START.isoformat(),
            "baseline_end": BASELINE_END.isoformat(),
            "method": "linear percentile of pooled daily maxima; strict exceedance; minimum 3 consecutive days",
        },
        "summary": {
            "total_events": len(events),
            "total_heatwave_days": len(event_days),
            "longest_event_days": max((e["duration_days"] for e in events), default=0),
            "peak_temperature_c": max(v for v in daily.values() if v is not None),
        },
        "annual_metrics": annual,
        "events": events,
        "trend": trend,
        "data_quality": quality,
        "baseline_data_quality": baseline_quality,
        "algorithm_version": ALGORITHM_VERSION,
    }

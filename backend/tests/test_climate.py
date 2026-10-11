from datetime import date, timedelta
import pytest
from app.services.climate import (
    detect_events,
    normalize,
    baseline_threshold,
    calculate_trend,
    analyze,
    DataQualityError,
    dates_between,
)


def series(values):
    return {date(2000, 1, 1) + timedelta(days=i): v for i, v in enumerate(values)}


@pytest.mark.parametrize(
    "values,count,durations",
    [
        ([31, 31], 0, []),
        ([31, 31, 31], 1, [3]),
        ([31, 31, 31, 20, 32, 32, 32, 32], 2, [3, 4]),
        ([31, 31, 20, 31, 31], 0, []),
        ([31, 31, None, 31, 31], 0, []),
        ([31, 30, 31], 0, []),
    ],
)
def test_detection(values, count, durations):
    events = detect_events(series(values), 30)
    assert len(events) == count
    assert [e["duration_days"] for e in events] == durations


def test_sparse_dates_break_sequence():
    assert detect_events({date(2000, 1, d): 40 for d in [1, 2, 4]}, 30) == []


def baseline():
    return [
        (d.isoformat(), float(i % 100))
        for i, d in enumerate(dates_between(date(1991, 1, 1), date(2020, 12, 31)))
    ]


def test_percentile_and_bad_baseline():
    rows = [(d, v / 2) for d, v in baseline()]
    threshold, quality = baseline_threshold(rows)
    import numpy as np

    assert threshold == pytest.approx(np.percentile([v for _, v in rows], 95))
    assert quality["coverage_percentage"] == 100
    with pytest.raises(DataQualityError):
        baseline_threshold(rows[:100])


def test_noisy_data():
    rows = [
        ("2000-01-01", 25),
        ("2000-01-01", 25),
        ("2000-01-02", 30),
        ("2000-01-02", 31),
        ("2000-01-03", 999),
        ("bad", 20),
        ("2000-01-04", float("nan")),
        ("2000-01-05", True),
    ]
    daily, quality = normalize(rows, date(2000, 1, 1), date(2000, 1, 6))
    assert list(daily.values()) == [25, None, None, None, None, None]
    assert quality["duplicate_rows"] == 2
    assert quality["conflicting_dates"] == 1
    assert quality["valid_days"] == 1
    assert quality["rejected_temperatures"] == 3


def test_cross_year_aggregation():
    base = [(d, 20) for d, _ in baseline()]
    rows = [
        (d.isoformat(), 30 if date(2000, 12, 30) <= d <= date(2001, 1, 2) else 10)
        for d in dates_between(date(2000, 1, 1), date(2001, 12, 31))
    ]
    result = analyze(rows, base, date(2000, 1, 1), date(2001, 12, 31))
    assert result["summary"]["total_events"] == 1
    assert [a["event_count"] for a in result["annual_metrics"]] == [1, 0]
    assert [a["heatwave_days"] for a in result["annual_metrics"]] == [2, 2]
    assert result["events"][0]["duration_days"] == 4
    assert result["annual_metrics"][0]["mean_event_duration_days"] == 4
    assert result["annual_metrics"][1]["mean_event_duration_days"] is None
    assert result["annual_metrics"][0]["mean_intensity_c"] == 10


def test_trend():
    rows = [
        {"year": 2000 + i, "event_count": i, "eligible_for_trend": True}
        for i in range(10)
    ]
    trend = calculate_trend(rows)
    assert trend["regression"]["slope_events_per_decade"] == pytest.approx(10)
    assert trend["comparison"]["percent_change"] == pytest.approx(250)
    assert rows[4]["rolling_5_year_events"] == 2
    rows[0]["eligible_for_trend"] = False
    assert calculate_trend(rows)["comparison"] is None


def test_zero_denominator_and_short_period():
    rows = [
        {"year": 2000 + i, "event_count": 0, "eligible_for_trend": True}
        for i in range(10)
    ]
    assert calculate_trend(rows)["comparison"]["percent_change"] is None
    assert calculate_trend(rows[:5])["regression"] is None


def test_partial_year_excluded():
    base = [(d, 20) for d, _ in baseline()]
    result = analyze([("2000-01-01", 30)], base, date(2000, 1, 1), date(2000, 1, 31))
    assert not result["annual_metrics"][0]["eligible_for_trend"]


def test_leap_day_is_real_calendar_adjacency():
    daily = {date(2000, 2, 28): 31, date(2000, 2, 29): 31, date(2000, 3, 1): 31}
    assert detect_events(daily, 30)[0]["duration_days"] == 3


def test_missing_years_do_not_compress_regression_time():
    rows = [
        {"year": 2000 + i * 2, "event_count": i, "eligible_for_trend": True}
        for i in range(10)
    ]
    assert calculate_trend(rows)["regression"][
        "slope_events_per_decade"
    ] == pytest.approx(5)


def test_all_missing_selected_period_fails():
    base = [(d, 20) for d, _ in baseline()]
    with pytest.raises(DataQualityError, match="No valid observations"):
        analyze([], base, date(2000, 1, 1), date(2000, 12, 31))

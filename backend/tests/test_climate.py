from datetime import date, timedelta

import pytest

from app.services.climate import (
    DataQualityError,
    analyze,
    baseline_threshold,
    calculate_trend,
    dates_between,
    detect_events,
    mann_kendall,
    normalize,
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
        ([31] * 10, 1, [10]),
        ([30, 30, 30], 0, []),
        ([31, 31, 31, 30, 31, 31, 31], 2, [3, 3]),
        ([31, 31, 31, None, 31, 31, 31], 2, [3, 3]),
        ([30.0001, 30.0001, 30.0001], 1, [3]),
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
    # First-window mean is 2.0 events/year, enough base for a percentage.
    assert trend["comparison"]["percent_change"] == pytest.approx(250)
    assert trend["mann_kendall"]["significant"]
    assert "250% change" in trend["insight"]
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


def eligible(counts, first_year=2000):
    return [
        {"year": first_year + i, "event_count": c, "eligible_for_trend": True}
        for i, c in enumerate(counts)
    ]


def test_near_zero_base_suppresses_percentage():
    # 1 event in the first five years versus 5 in the last: +400% would mislead.
    trend = calculate_trend(eligible([0, 0, 1, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]))
    assert trend["comparison"]["first_mean"] == pytest.approx(0.2)
    assert trend["comparison"]["percent_change"] is None
    assert "%" not in trend["insight"]


def test_noisy_small_counts_report_no_significant_trend():
    # Shape of the live Hyderabad result: 1.2 -> 0.4 events/year, pure noise.
    trend = calculate_trend(eligible([2, 0, 3, 0, 1, 1, 2, 0, 1, 2, 0, 1, 0, 1, 0]))
    assert not trend["mann_kendall"]["significant"]
    assert "no statistically significant" in trend["insight"]
    assert "%" not in trend["insight"]


def test_mann_kendall_known_values():
    result = mann_kendall(list(range(10)), list(range(10)))
    assert result["s"] == 45
    assert result["sen_slope_per_decade"] == pytest.approx(10)
    assert result["p_value"] < 0.001
    assert mann_kendall(list(range(10)), [5] * 10)["p_value"] == 1.0
    assert mann_kendall(list(range(9)), list(range(9))) is None


def test_mann_kendall_is_robust_to_one_outlier():
    counts = [1] * 14 + [40]
    result = mann_kendall(list(range(15)), counts)
    assert result["sen_slope_per_decade"] == 0
    assert not result["significant"]


def test_single_year_has_no_trend():
    base = [(d, 20) for d, _ in baseline()]
    rows = [
        (d.isoformat(), 25) for d in dates_between(date(2010, 1, 1), date(2010, 12, 31))
    ]
    result = analyze(rows, base, date(2010, 1, 1), date(2010, 12, 31))
    assert result["trend"]["regression"] is None
    assert result["trend"]["mann_kendall"] is None
    assert result["trend"]["comparison"] is None
    assert "Insufficient" in result["trend"]["insight"]
    assert result["annual_metrics"][0]["heatwave_days"] == 365


def test_extreme_but_plausible_values_are_kept():
    rows = [("2000-01-01", -89.0), ("2000-01-02", 64.9), ("2000-01-03", 65.1)]
    daily, quality = normalize(rows, date(2000, 1, 1), date(2000, 1, 3))
    assert list(daily.values()) == [-89.0, 64.9, None]
    assert quality["rejected_temperatures"] == 1


def test_leap_year_coverage_uses_366_days():
    base = [(d, 20) for d, _ in baseline()]
    rows = [
        (d.isoformat(), 25) for d in dates_between(date(2000, 1, 1), date(2000, 12, 30))
    ]
    result = analyze(rows, base, date(2000, 1, 1), date(2000, 12, 31))
    year = result["annual_metrics"][0]
    assert year["coverage_percentage"] == round(100 * 365 / 366, 2)
    assert year["eligible_for_trend"]

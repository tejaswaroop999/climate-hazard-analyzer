import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import type { AnnualMetric } from "../types";
export default function Charts({ rows }: { rows: AnnualMetric[] }) {
  return (
    <div className="chart-grid">
      <section className="panel">
        <div className="panel-title">
          <div>
            <p className="eyebrow">FREQUENCY</p>
            <h2>Heatwaves over time</h2>
          </div>
          <span className="badge">Events / year</span>
        </div>
        <p className="chart-description">
          Bars show observed events. Lines show the trailing five-year mean and
          regression.
        </p>
        <div
          className="chart"
          role="img"
          aria-label="Heatwave events by year with rolling average and regression. Exact values are available in annual data below."
        >
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart
              data={rows}
              margin={{ top: 12, right: 12, left: -20, bottom: 4 }}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="year" minTickGap={35} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Legend />
              <Bar
                dataKey="event_count"
                name="Observed events"
                fill="#28735f"
                radius={[3, 3, 0, 0]}
              />
              <Line
                type="linear"
                dataKey="rolling_5_year_events"
                name="5-year mean"
                stroke="#e3a23a"
                strokeWidth={3}
                dot={false}
              />
              <Line
                dataKey="regression_events"
                name="Regression"
                stroke="#64748b"
                strokeDasharray="5 5"
                dot={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </section>
      <section className="panel">
        <div className="panel-title">
          <div>
            <p className="eyebrow">EXPOSURE</p>
            <h2>Days &amp; intensity</h2>
          </div>
          <span className="badge">Annual metrics</span>
        </div>
        <p className="chart-description">
          Intensity is the mean excess above the threshold on heatwave days.
        </p>
        <div
          className="chart"
          role="img"
          aria-label="Annual heatwave days and mean intensity above threshold"
        >
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart
              data={rows}
              margin={{ top: 12, right: 0, left: -20, bottom: 4 }}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="year" minTickGap={35} />
              <YAxis yAxisId="days" allowDecimals={false} />
              <YAxis
                yAxisId="intensity"
                orientation="right"
                unit=" C"
                width={55}
              />
              <Tooltip />
              <Legend />
              <Bar
                yAxisId="days"
                dataKey="heatwave_days"
                name="Heatwave days"
                fill="#a9cbbb"
                radius={[3, 3, 0, 0]}
              />
              <Line
                yAxisId="intensity"
                dataKey="mean_intensity_c"
                name="Mean intensity (C)"
                stroke="#b66635"
                strokeWidth={2}
                dot={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </section>
      <section className="panel duration-chart">
        <div className="panel-title">
          <div>
            <p className="eyebrow">DURATION</p>
            <h2>How long events last</h2>
          </div>
          <span className="badge">Days / event</span>
        </div>
        <p className="chart-description">
          Mean and longest event duration by start year. Years without events
          have no duration value.
        </p>
        <div
          className="chart"
          role="img"
          aria-label="Mean and maximum heatwave event duration by start year"
        >
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart
              data={rows}
              margin={{ top: 12, right: 12, left: -20, bottom: 4 }}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="year" minTickGap={35} />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line
                dataKey="mean_event_duration_days"
                name="Mean duration (days)"
                stroke="#28735f"
                strokeWidth={2}
                dot={false}
              />
              <Line
                dataKey="max_event_duration_days"
                name="Longest duration (days)"
                stroke="#b66635"
                strokeDasharray="5 5"
                dot={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  );
}

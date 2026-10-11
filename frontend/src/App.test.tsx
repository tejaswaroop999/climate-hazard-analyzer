import {
  fireEvent,
  render,
  screen,
  waitFor,
  cleanup,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import * as api from "./api";
vi.mock("./api", () => ({ analyze: vi.fn(), searchRegions: vi.fn() }));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});
describe("analysis form", () => {
  it("starts with no fabricated results and heatwave selected", () => {
    render(<App />);
    expect(screen.getByLabelText("Hazard")).toHaveValue("heatwave");
    expect(
      screen.getByText("Start with a place you know."),
    ).toBeInTheDocument();
  });
  it("shows a safe API failure and allows retry", async () => {
    vi.mocked(api.analyze).mockRejectedValue(
      new Error("Weather provider is unavailable"),
    );
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /Analyze heatwaves/ }));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Weather provider is unavailable",
      ),
    );
    expect(
      screen.getByRole("button", { name: /Analyze heatwaves/ }),
    ).toBeEnabled();
    expect(api.analyze).toHaveBeenCalledWith(
      expect.objectContaining({ hazard: "heatwave", latitude: 17.385 }),
      expect.any(AbortSignal),
    );
  });
  it("rejects reversed periods without an API call", () => {
    render(<App />);
    fireEvent.change(screen.getByLabelText("Start year"), {
      target: { value: "2020" },
    });
    fireEvent.change(screen.getByLabelText("End year"), {
      target: { value: "2000" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Analyze heatwaves/ }));
    expect(screen.getByRole("alert")).toHaveTextContent("ordered range");
    expect(api.analyze).not.toHaveBeenCalled();
  });
});

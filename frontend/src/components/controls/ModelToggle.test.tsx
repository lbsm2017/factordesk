import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { downloadHref, reportParams, uploadBody } from "../../api/queries";
import { EMPTY_URL_STATE } from "../../state/url";
import { ModelToggle } from "./ModelToggle";

describe("ModelToggle", () => {
  it("is a radio group with the range chips' markup and the selected model checked", () => {
    const { container } = render(<ModelToggle selected="ff6" onSelect={vi.fn()} />);
    const group = screen.getByRole("group", { name: "Factor model" });
    expect(group.tagName).toBe("FIELDSET");
    expect(group.className).toBe("ctl-range");
    expect(container.querySelectorAll(".seg-range > label.seg-opt")).toHaveLength(2);
    expect((screen.getByRole("radio", { name: "FF6" }) as HTMLInputElement).checked).toBe(true);
    expect((screen.getByRole("radio", { name: "FF5" }) as HTMLInputElement).checked).toBe(false);
  });

  it("reports the model picked", () => {
    const onSelect = vi.fn();
    render(<ModelToggle selected="ff6" onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("radio", { name: "FF5" }));
    expect(onSelect).toHaveBeenCalledWith("ff5");
  });
});

describe("model in the requests", () => {
  const spy = { ...EMPTY_URL_STATE, ticker: "SPY", range: "3Y" as const };

  it("always names the model in the report and download queries, because the API default is FF5", () => {
    expect(reportParams(spy)).toEqual({ range: "3Y", model: "ff6" });
    expect(reportParams({ ...spy, model: "ff5" })).toEqual({ range: "3Y", model: "ff5" });
    expect(reportParams({ ...EMPTY_URL_STATE, ticker: "SPY" })).toEqual({ range: "10Y", model: "ff6" });
    expect(reportParams({ ...spy, range: null, start: "2023-01-02", model: "ff5" })).toEqual({ start: "2023-01-02", model: "ff5" });
    expect(downloadHref(spy)).toBe("/api/report/SPY/html?range=3Y&model=ff6");
    expect(downloadHref({ ...spy, model: "ff5" })).toBe("/api/report/SPY/html?range=3Y&model=ff5");
  });

  it("always sends the model form field of the upload", () => {
    const file = new File(["date,return\n"], "r.csv", { type: "text/csv" });
    expect(uploadBody({ file, name: "", grossNet: "" }).get("model")).toBe("ff6");
    expect(uploadBody({ file, name: "", grossNet: "", model: "ff5" }).get("model")).toBe("ff5");
    expect(uploadBody({ file, name: "", grossNet: "", model: "ff6" }).get("model")).toBe("ff6");
  });
});

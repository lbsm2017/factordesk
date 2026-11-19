import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { downloadHref, reportParams, uploadBody } from "../../api/queries";
import { EMPTY_URL_STATE } from "../../state/url";
import { ModelToggle } from "./ModelToggle";

describe("ModelToggle", () => {
  it("is a radio group with the range chips' markup and FF5 selected by default", () => {
    const { container } = render(<ModelToggle selected="ff5" onSelect={vi.fn()} />);
    const group = screen.getByRole("group", { name: "Factor model" });
    expect(group.tagName).toBe("FIELDSET");
    expect(group.className).toBe("ctl-range");
    expect(container.querySelectorAll(".seg-range > label.seg-opt")).toHaveLength(2);
    expect((screen.getByRole("radio", { name: "FF5" }) as HTMLInputElement).checked).toBe(true);
    expect((screen.getByRole("radio", { name: "FF6" }) as HTMLInputElement).checked).toBe(false);
  });

  it("reports the model picked", () => {
    const onSelect = vi.fn();
    render(<ModelToggle selected="ff5" onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("radio", { name: "FF6" }));
    expect(onSelect).toHaveBeenCalledWith("ff6");
  });
});

describe("model in the requests", () => {
  const spy = { ...EMPTY_URL_STATE, ticker: "SPY", range: "3Y" as const };

  it("adds model=ff6 to the report and download queries for FF6 only", () => {
    expect(reportParams(spy)).toEqual({ range: "3Y" });
    expect(reportParams({ ...spy, model: "ff6" })).toEqual({ range: "3Y", model: "ff6" });
    expect(reportParams({ ...spy, range: null, start: "2023-01-02", model: "ff6" })).toEqual({ start: "2023-01-02", model: "ff6" });
    expect(downloadHref(spy)).toBe("/api/report/SPY/html?range=3Y");
    expect(downloadHref({ ...spy, model: "ff6" })).toBe("/api/report/SPY/html?range=3Y&model=ff6");
  });

  it("sends the model form field of the upload for FF6 only", () => {
    const file = new File(["date,return\n"], "r.csv", { type: "text/csv" });
    expect(uploadBody({ file, name: "", grossNet: "" }).has("model")).toBe(false);
    expect(uploadBody({ file, name: "", grossNet: "", model: "ff5" }).has("model")).toBe(false);
    expect(uploadBody({ file, name: "", grossNet: "", model: "ff6" }).get("model")).toBe("ff6");
  });
});

import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { Switch } from "./Switch";

function Harness() {
  const [on, setOn] = useState(false);
  return <Switch label="Show statistics" hint="t, p-values, intervals" checked={on} onChange={setOn} />;
}

describe("Switch (design K.1)", () => {
  it("is a native button with role switch, named by its visible label only", () => {
    render(<Harness />);
    const sw = screen.getByRole("switch", { name: "Show statistics" });
    expect(sw.tagName).toBe("BUTTON");
    expect(sw.getAttribute("type")).toBe("button");
    expect(sw.getAttribute("aria-checked")).toBe("false");
    expect(sw.querySelector(".sw-hint")?.getAttribute("aria-hidden")).toBe("true");
  });

  it("toggles on activation (Space and Enter activate a native button)", () => {
    render(<Harness />);
    const sw = screen.getByRole("switch", { name: "Show statistics" });
    fireEvent.click(sw);
    expect(sw.getAttribute("aria-checked")).toBe("true");
    fireEvent.click(sw);
    expect(sw.getAttribute("aria-checked")).toBe("false");
  });

  it("reports the next value", () => {
    const onChange = vi.fn();
    render(<Switch label="X" checked onChange={onChange} />);
    fireEvent.click(screen.getByRole("switch", { name: "X" }));
    expect(onChange).toHaveBeenCalledWith(false);
  });
});

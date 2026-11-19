import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Panel } from "./Panel";

const state = vi.hoisted(() => ({ stats: false }));
vi.mock("../../state/stats", () => ({ useShowStats: () => state.stats }));

function classOf(id: string): string {
  const { container } = render(<Panel id={id} title="T" />);
  return container.querySelector("section")?.className ?? "";
}

describe("panels that share a row", () => {
  it("pairs Price with Drawdown, and Alpha across models with World beta in two equal halves", () => {
    state.stats = false;
    expect(classOf("price")).toBe("panel s-7");
    expect(classOf("performance")).toBe("panel s-5");
    expect(classOf("alpha-strip")).toBe("panel s-6");
    expect(classOf("world-beta")).toBe("panel s-6");
  });

  it("gives World beta the full row with statistics on, since it then has six columns", () => {
    state.stats = true;
    expect(classOf("world-beta")).toBe("panel");
    expect(classOf("alpha-strip")).toBe("panel s-6");
    state.stats = false;
  });

  it("keeps the nav order: Alpha across models comes right before World beta", async () => {
    const { PANELS } = await import("./panelRegistry");
    const names = [...PANELS].sort((a, b) => a.position - b.position).map((p) => p.name);
    expect(names.indexOf("world_beta") - names.indexOf("alpha_strip")).toBe(1);
  });
});

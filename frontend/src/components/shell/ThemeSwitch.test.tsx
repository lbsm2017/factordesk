import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Sidebar } from "./Sidebar";

afterEach(() => {
  window.localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});

function sidebar() {
  return render(
    <Sidebar open={false} root={null} report={undefined} onClose={() => undefined} onNavigate={() => undefined}>
      <div />
    </Sidebar>,
  );
}

describe("theme switch in the sidebar footer", () => {
  it("offers System, Light and Dark, with System on by default", () => {
    sidebar();
    const group = screen.getByRole("group", { name: "Theme" });
    expect(group.closest(".side-foot")).not.toBeNull();
    expect((screen.getByRole("radio", { name: "System" }) as HTMLInputElement).checked).toBe(true);
    expect(screen.getAllByRole("radio", { name: /System|Light|Dark/ })).toHaveLength(3);
  });

  it("sets data-theme and remembers the choice", () => {
    sidebar();
    fireEvent.click(screen.getByRole("radio", { name: "Dark" }));
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(window.localStorage.getItem("factordesk.theme")).toBe("dark");
    fireEvent.click(screen.getByRole("radio", { name: "System" }));
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
  });
});

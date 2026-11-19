import { describe, expect, it } from "vitest";
import { renameTree } from "./composer";
import { buildPreset } from "./presets";
import {
  EMPTY_STORE,
  MAX_SAVED,
  STORAGE_KEY,
  cleanName,
  copyName,
  loadStore,
  parseStored,
  reduce,
  saveStore,
  serialise,
} from "./store";
import type { StoreAction, StoreState } from "./store";
import { LIBRARY } from "./testLibrary";
import { emptyTree } from "./tree";

function apply(state: StoreState, ...actions: StoreAction[]): StoreState {
  return actions.reduce(reduce, state);
}

const A = emptyTree("Alpha");
const B = emptyTree("Beta");
const C = emptyTree("Gamma");

function three(): StoreState {
  return apply(
    EMPTY_STORE,
    { type: "create", id: "a", tree: A },
    { type: "create", id: "b", tree: B },
    { type: "create", id: "c", tree: C },
  );
}

class MemoryStorage {
  data = new Map<string, string>();
  getItem(key: string) {
    return this.data.get(key) ?? null;
  }
  setItem(key: string, value: string) {
    this.data.set(key, value);
  }
}

describe("saved portfolios", () => {
  it("creates and selects", () => {
    const s = three();
    expect(s.portfolios.map((p) => p.id)).toEqual(["a", "b", "c"]);
    expect(s.activeId).toBe("c");
    expect(apply(s, { type: "select", id: "a" }).activeId).toBe("a");
    expect(apply(s, { type: "select", id: "zzz" })).toBe(s);
  });

  it("edits one portfolio", () => {
    const s = apply(three(), { type: "edit", id: "b", tree: { ...B, cost_bps: 25 } });
    expect(s.portfolios.find((p) => p.id === "b")?.tree.cost_bps).toBe(25);
    expect(s.portfolios.find((p) => p.id === "a")?.tree.cost_bps).toBe(0);
  });

  it("duplicates next to the source, with a free copy name, and selects the copy", () => {
    let s = apply(three(), { type: "duplicate", id: "a", newId: "a2" });
    expect(s.portfolios.map((p) => p.id)).toEqual(["a", "a2", "b", "c"]);
    expect(s.portfolios[1]?.tree.name).toBe("Alpha copy");
    expect(s.portfolios[1]?.tree.root.label).toBe("Alpha copy");
    expect(s.activeId).toBe("a2");
    s = apply(s, { type: "duplicate", id: "a", newId: "a3" });
    expect(s.portfolios.find((p) => p.id === "a3")?.tree.name).toBe("Alpha copy 2");
    expect(copyName("Alpha copy", ["Alpha", "Alpha copy"])).toBe("Alpha copy 2");
  });

  it("renames, and refuses a blank name", () => {
    const s = apply(three(), { type: "rename", id: "a", name: "  Renamed  " });
    expect(s.portfolios[0]?.tree.name).toBe("Renamed");
    expect(apply(s, { type: "rename", id: "a", name: "   " })).toBe(s);
    expect(cleanName("x".repeat(100))).toHaveLength(80);
    expect(cleanName(" ")).toBeNull();
  });

  it("deletes at once and brings it back with Undo, in the same place", () => {
    const s = apply(three(), { type: "select", id: "b" }, { type: "delete", id: "b" });
    expect(s.portfolios.map((p) => p.id)).toEqual(["a", "c"]);
    expect(s.activeId).toBe("c");
    expect(s.deleted?.item.tree.name).toBe("Beta");
    const back = apply(s, { type: "undo" });
    expect(back.portfolios.map((p) => p.id)).toEqual(["a", "b", "c"]);
    expect(back.activeId).toBe("b");
    expect(back.deleted).toBeNull();
  });

  it("moves to the previous portfolio when the last one is deleted, and to none when all are gone", () => {
    const s = apply(three(), { type: "delete", id: "c" });
    expect(s.activeId).toBe("b");
    const none = apply(s, { type: "delete", id: "a" }, { type: "delete", id: "b" });
    expect(none.activeId).toBeNull();
    expect(apply(none, { type: "undo" }).portfolios.map((p) => p.id)).toEqual(["b"]);
  });

  it("keeps the active portfolio when another one is deleted, and a dismissed undo is gone", () => {
    const s = apply(three(), { type: "delete", id: "a" });
    expect(s.activeId).toBe("c");
    const dismissed = apply(s, { type: "dismissUndo" });
    expect(dismissed.deleted).toBeNull();
    expect(apply(dismissed, { type: "undo" })).toBe(dismissed);
    expect(apply(s, { type: "delete", id: "nope" })).toBe(s);
  });

  it("creating after a delete drops the undo, and the list is capped", () => {
    const s = apply(three(), { type: "delete", id: "a" }, { type: "create", id: "d", tree: A });
    expect(s.deleted).toBeNull();
    let full = EMPTY_STORE;
    for (let i = 0; i < MAX_SAVED + 5; i++) full = reduce(full, { type: "create", id: `p${i}`, tree: A });
    expect(full.portfolios).toHaveLength(MAX_SAVED);
  });
});

describe("storage", () => {
  it("round-trips the portfolios and the active one, and never stores the undo", () => {
    const tree = buildPreset("saa", "Balanced SAA", LIBRARY);
    const s = apply(three(), { type: "create", id: "d", tree }, { type: "select", id: "b" }, { type: "delete", id: "a" });
    const memory = new MemoryStorage();
    expect(saveStore(s, memory)).toBe(true);
    expect(memory.data.has(STORAGE_KEY)).toBe(true);
    const back = loadStore(memory);
    expect(back.portfolios).toEqual(s.portfolios);
    expect(back.activeId).toBe("b");
    expect(back.deleted).toBeNull();
  });

  it("uses a versioned key", () => {
    expect(STORAGE_KEY).toMatch(/\.v1$/);
  });

  it("gives the empty store for nothing, bad JSON, another version or a wrong shape", () => {
    expect(parseStored(null)).toEqual(EMPTY_STORE);
    expect(parseStored("{not json")).toEqual(EMPTY_STORE);
    expect(parseStored(JSON.stringify({ version: 2, portfolios: [] }))).toEqual(EMPTY_STORE);
    expect(parseStored(JSON.stringify({ version: 1, portfolios: "x" }))).toEqual(EMPTY_STORE);
    expect(parseStored("[]")).toEqual(EMPTY_STORE);
  });

  it("drops a bad entry and a repeated id, and falls back to the first active", () => {
    const good = { id: "a", tree: A };
    const text = JSON.stringify({
      version: 1,
      activeId: "gone",
      portfolios: [good, { id: "x", tree: { version: 1, name: 3 } }, { id: "a", tree: B }, 7],
    });
    const s = parseStored(text);
    expect(s.portfolios).toEqual([good]);
    expect(s.activeId).toBe("a");
  });

  it("survives a storage that throws on read, on write, or on access", () => {
    const broken = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("full");
      },
    };
    expect(loadStore(broken)).toEqual(EMPTY_STORE);
    expect(saveStore(three(), broken)).toBe(false);
    expect(loadStore(null)).toEqual(EMPTY_STORE);
    expect(saveStore(three(), null)).toBe(false);
  });

  it("serialises only the list and the active id", () => {
    const data = JSON.parse(serialise(apply(three(), { type: "delete", id: "a" }))) as Record<string, unknown>;
    expect(Object.keys(data).sort()).toEqual(["activeId", "portfolios", "version"]);
  });

  it("keeps a renamed tree through the round trip", () => {
    const s = apply(three(), { type: "edit", id: "a", tree: renameTree(A, "New") });
    expect(parseStored(serialise(s)).portfolios[0]?.tree.name).toBe("New");
  });
});

import { describe, expect, it } from "vitest";
import { BOM, CSV_COLUMNS, formatCsvError, parsePortfolioCsv, treeToCsv, uniqueName, weightToPct } from "./csv";
import type { CsvError, CsvImport } from "./csv";
import { PRESETS, buildPreset } from "./presets";
import { LIBRARY, lib } from "./testLibrary";
import { addInstrument, addLine, instruments, normalise, setWeight, swapInstrument, totalWeight } from "./tree";
import type { PortfolioTree } from "./tree";

const HEADER = CSV_COLUMNS.join(",");

function parse(text: string): CsvImport {
  return parsePortfolioCsv(text, LIBRARY, "File name");
}

function ok(text: string): PortfolioTree {
  const result = parse(text);
  if (!result.ok) throw new Error(result.errors.map(formatCsvError).join("; "));
  return result.tree;
}

function errors(text: string): string[] {
  const result = parse(text);
  if (result.ok) throw new Error("expected errors");
  return result.errors.map(formatCsvError);
}

describe("round trip", () => {
  it.each(PRESETS.map((p) => p.id))("export then import gives the same tree: %s", (id) => {
    const tree = buildPreset(id, "My portfolio", LIBRARY);
    expect(ok(treeToCsv(tree))).toEqual(tree);
  });

  it("each preset exports one row per instrument under the header", () => {
    for (const preset of PRESETS) {
      const lines = treeToCsv(buildPreset(preset.id, "A", LIBRARY)).trimEnd().split("\n");
      expect(lines.slice(0, 3)).toEqual(["# name: A", "# cost_bps: 10", HEADER]);
      expect(lines.length - 3).toBe(preset.lines.length);
    }
  });

  it("writes the cash line with the ticker RF and reads it back as cash", () => {
    const tree = buildPreset("saa", "A", LIBRARY);
    const cashRow = treeToCsv(tree).split("\n").find((l) => l.includes(",cash_usd,"));
    expect(cashRow).toBe("Cash,USD Cash,cash_usd,RF,2");
    const cash = instruments(ok(treeToCsv(tree))).find((i) => i.kind === "cash");
    expect(cash?.ticker).toBeNull();
    expect(cash?.weight).toBeCloseTo(0.02, 12);
  });

  it("keeps a name with a comma, quotes and a changed cost", () => {
    const base = buildPreset("6040", 'Growth, "core" 60/40', LIBRARY);
    const tree = { ...base, cost_bps: 2.5 };
    expect(ok(treeToCsv(tree))).toEqual(tree);
  });

  it("keeps a swapped ticker, a second instrument in one line, a line with no proxy and uneven weights", () => {
    let tree = buildPreset("blank", "Mixed", LIBRARY);
    tree = addLine(tree, lib("eq_na_large"));
    tree = swapInstrument(tree, "eq_na_large_i_1", "SPY");
    tree = addInstrument(tree, "sub_eq_na_large", "QQQ");
    tree = setWeight(tree, "eq_na_large_i_1", 1 / 3);
    tree = setWeight(tree, "eq_na_large_i_2", 1 / 7);
    tree = addLine(tree, lib("alt_vc")); // no proxy, weight 0
    tree = addLine(tree, lib("com_gold"));
    tree = setWeight(tree, "com_gold_i_1", 0.123456789);
    tree = normalise(tree);
    const back = ok(treeToCsv(tree));
    expect(instruments(back).map((i) => [i.id, i.kind, i.ticker, i.label])).toEqual(
      instruments(tree).map((i) => [i.id, i.kind, i.ticker, i.label]),
    );
    instruments(tree).forEach((inst, k) => {
      expect(instruments(back)[k]?.weight).toBeCloseTo(inst.weight, 10);
    });
    expect(totalWeight(back)).toBeCloseTo(1, 9);
    expect(back.root).toMatchObject({ children: tree.root.children.map((ac) => ({ id: ac.id, label: ac.label })) });
  });

  it("formats a weight without float noise", () => {
    expect(weightToPct(0.33)).toBe("33");
    expect(weightToPct(0.125)).toBe("12.5");
    expect(weightToPct(0)).toBe("0");
    expect(weightToPct(1)).toBe("100");
  });
});

describe("reading a file", () => {
  it("accepts quoted fields with commas, doubled quotes and a line break", () => {
    const tree = ok(
      [
        "# name: Quoted",
        HEADER,
        '"Equities, large","Equity N. America - ""Large"" Cap",eq_na_large,IVV,"60"',
        'Fixed Income,"Government\nBonds",fi_na_gov,IEF,40',
      ].join("\n"),
    );
    expect(tree.name).toBe("Quoted");
    expect(instruments(tree).map((i) => [i.ticker, i.weight])).toEqual([
      ["IVV", 0.6],
      ["IEF", 0.4],
    ]);
    // The group names come from the library, not from the file.
    expect(tree.root.children.map((ac) => ac.label)).toEqual(["Equities", "Fixed Income"]);
  });

  it("takes CRLF line endings, a byte order mark, blank lines and a name from the fallback", () => {
    const tree = ok(`${BOM}${HEADER}\r\n\r\nEquities,x,eq_na_large,IVV,50\r\n,,,,\r\n`);
    expect(tree.name).toBe("File name");
    expect(tree.cost_bps).toBe(10);
    expect(totalWeight(tree)).toBe(0.5);
  });

  it("takes the header columns in any order and ignores extra columns", () => {
    const tree = ok("weight_pct,note,line_id,ticker,asset_class,sub_asset_class\n25,hello,com_gold,GLD,a,b");
    expect(instruments(tree).map((i) => [i.ticker, i.weight])).toEqual([["GLD", 0.25]]);
  });

  it("takes a weight with a percent sign or a decimal comma", () => {
    const tree = ok(`${HEADER}\nx,y,eq_na_large,IVV,12.5 %\nx,y,fi_na_gov,IEF,"7,5"`);
    expect(instruments(tree).map((i) => i.weight)).toEqual([0.125, 0.075]);
  });

  it("groups rows of one line that are not next to each other", () => {
    const tree = ok(`${HEADER}\nx,y,eq_na_large,IVV,10\nx,y,fi_na_gov,IEF,10\nx,y,eq_na_large,SPY,10`);
    expect(tree.root.children.map((ac) => ac.children.map((s) => s.children.map((i) => i.ticker)))).toEqual([
      [["IVV", "SPY"]],
      [["IEF"]],
    ]);
  });

  it("reads the name and the cost from the comment lines", () => {
    const tree = ok(`# name: Mine, with commas\n# cost_bps: 25\n${HEADER}`);
    expect(tree.name).toBe("Mine, with commas");
    expect(tree.cost_bps).toBe(25);
    expect(tree.root.label).toBe("Mine, with commas");
    expect(instruments(tree)).toEqual([]);
  });
});

describe("errors, with their line number", () => {
  const rows = (...lines: string[]) => [HEADER, ...lines].join("\n");

  it("a weight that is not a number", () => {
    expect(errors(rows("x,y,eq_na_large,IVV,60", "x,y,fi_na_gov,IEF,forty"))).toEqual([
      "Line 3: weight is not a number",
    ]);
  });

  it("counts comment lines and blank lines", () => {
    expect(errors(`# name: A\n# cost_bps: 10\n${HEADER}\n\nx,y,eq_na_large,IVV,abc`)).toEqual([
      "Line 5: weight is not a number",
    ]);
  });

  it("counts the lines inside a quoted field", () => {
    expect(errors(`${HEADER}\n"a\nb\nc",y,eq_na_large,IVV,10\nx,y,fi_na_gov,IEF,zz`)).toEqual([
      "Line 5: weight is not a number",
    ]);
  });

  it("a missing weight and a weight out of range", () => {
    expect(errors(rows("x,y,eq_na_large,IVV,", "x,y,fi_na_gov,IEF,101", "x,y,com_gold,GLD,-1"))).toEqual([
      "Line 2: weight is missing",
      "Line 3: weight must be from 0 to 100",
      "Line 4: weight must be from 0 to 100",
    ]);
  });

  it("a line_id that is missing or not in the library", () => {
    expect(errors(rows("x,y,,IVV,10", "x,y,eq_mars,IVV,10"))).toEqual([
      "Line 2: line_id is missing",
      'Line 3: line_id "eq_mars" is not in the Asset Class Library',
    ]);
  });

  it("refuses a line_id that is not a library line even when the names look right", () => {
    const result = parse(rows("Equities,Equity N. America - Large Cap,my_own_line,IVV,10"));
    expect(result.ok).toBe(false);
    expect((result as { errors: CsvError[] }).errors).toEqual([
      { line: 2, message: 'line_id "my_own_line" is not in the Asset Class Library' },
    ]);
  });

  it("a ticker that is not valid, and RF outside a cash line", () => {
    expect(errors(rows("x,y,eq_na_large,I V V,10", "x,y,fi_na_gov,RF,10"))).toEqual([
      'Line 2: ticker "I V V" is not a valid ticker',
      "Line 3: ticker RF (the risk-free rate) is only for a cash line",
    ]);
  });

  it("a weight on a line with no ticker", () => {
    expect(errors(rows("x,y,alt_vc,,5"))).toEqual(["Line 2: a line with no ticker cannot take a weight"]);
    expect(ok(rows("x,y,alt_vc,,0")).root.children).toHaveLength(1);
  });

  it("a row with too few or too many columns", () => {
    const [few, many] = errors(rows("x,y,eq_na_large,IVV", "x,y,eq_na_large,IVV,10,extra"));
    expect(few).toMatch(/^Line 2: expected 5 columns but found 4/);
    expect(many).toMatch(/^Line 3: expected 5 columns but found 6/);
  });

  it("a header with missing columns", () => {
    expect(errors("asset_class,line_id,ticker\nx,eq_na_large,IVV")).toEqual([
      "Line 1: the header row is missing sub_asset_class, weight_pct",
    ]);
  });

  it("a file with no header at all", () => {
    expect(errors("")).toEqual([`The file has no header row. Expected ${HEADER}.`]);
    expect(errors("# name: Only a comment")).toEqual([`The file has no header row. Expected ${HEADER}.`]);
  });

  it("a quoted field that is not closed, and text after a closing quote", () => {
    expect(errors(`${HEADER}\nx,y,eq_na_large,"IVV,10\nmore`)).toEqual(["Line 2: a quoted field is not closed"]);
    expect(errors(`${HEADER}\nx,"y"z,eq_na_large,IVV,10`)).toEqual(["Line 2: unexpected text after a closing quote"]);
  });

  it("a bad cost or a name that is too long", () => {
    expect(errors(`# cost_bps: lots\n${HEADER}`)).toEqual(["Line 1: cost_bps is not a number"]);
    expect(errors(`# name: A\n# cost_bps: 1001\n${HEADER}`)).toEqual(["Line 2: cost_bps must be between 0 and 1000"]);
    expect(errors(`# name: ${"n".repeat(81)}\n${HEADER}`)).toEqual(["Line 1: name is longer than 80 characters"]);
  });

  it("reports every bad row, not only the first", () => {
    expect(errors(rows("x,y,eq_na_large,IVV,a", "x,y,fi_na_gov,IEF,b", "x,y,com_gold,GLD,c"))).toHaveLength(3);
  });

  it("weights above 100% in total and more than 50 instruments come from the composer validation", () => {
    expect(errors(rows("x,y,eq_na_large,IVV,70", "x,y,fi_na_gov,IEF,40"))).toEqual([
      "The weights add up to 110.00%, which is more than 100%.",
    ]);
    const many = Array.from({ length: 51 }, () => "x,y,eq_na_large,IVV,0");
    expect(errors(rows(...many))).toEqual(["At most 50 instruments are allowed, got 51."]);
  });
});

describe("uniqueName", () => {
  it("keeps a free name and numbers a taken one within 80 characters", () => {
    expect(uniqueName("Growth", ["Other"])).toBe("Growth");
    expect(uniqueName("Growth", ["Growth"])).toBe("Growth (2)");
    expect(uniqueName("Growth", ["Growth", "Growth (2)"])).toBe("Growth (3)");
    const long = "n".repeat(80);
    expect(uniqueName(long, [long])).toHaveLength(80);
  });
});

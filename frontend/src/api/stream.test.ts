import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiRequestError } from "./client";
import { parseSse, streamReport } from "./stream";
import type { SseMessage } from "./stream";
import type { ProgressStep } from "./types";

const encoder = new TextEncoder();

function streamOf(chunks: (string | Uint8Array)[]): ReadableStream<Uint8Array> {
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(typeof chunk === "string" ? encoder.encode(chunk) : chunk);
      controller.close();
    },
  });
}

async function collect(chunks: (string | Uint8Array)[]): Promise<SseMessage[]> {
  const out: SseMessage[] = [];
  for await (const message of parseSse(streamOf(chunks))) out.push(message);
  return out;
}

const step = (index: number, total: number, id: ProgressStep["step"], label: string): ProgressStep => ({
  step: id,
  label,
  index,
  total,
});
const block = (event: string, data: unknown) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;

describe("parseSse", () => {
  it("reads step, report and error blocks", async () => {
    const messages = await collect([
      block("step", step(1, 2, "prices", "Downloading prices")),
      block("report", { ticker: "SPY" }),
      block("error", { code: "internal", message: "m", action: "a", status: 500 }),
    ]);
    expect(messages.map((m) => m.event)).toEqual(["step", "report", "error"]);
    expect(JSON.parse(messages[0]?.data ?? "")).toEqual(step(1, 2, "prices", "Downloading prices"));
  });

  it("skips comment lines such as keep-alive", async () => {
    const messages = await collect([": keep-alive\n\n", block("step", step(1, 1, "prices", "x")), ": keep-alive\n\n"]);
    expect(messages).toHaveLength(1);
    expect(messages[0]?.event).toBe("step");
  });

  it("joins the pieces of a block that arrives in split chunks, even inside a line", async () => {
    const text = block("step", step(2, 4, "factors", "Loading factor data"));
    const cut = [text.slice(0, 7), text.slice(7, 19), text.slice(19, 40), text.slice(40)];
    const messages = await collect(cut);
    expect(messages).toHaveLength(1);
    expect(JSON.parse(messages[0]?.data ?? "").label).toBe("Loading factor data");
  });

  it("splits one chunk that holds several blocks", async () => {
    const text = block("step", step(1, 2, "prices", "a")) + block("step", step(2, 2, "models", "b"));
    expect(await collect([text])).toHaveLength(2);
  });

  it("handles CRLF line ends, also when the CR and the LF arrive in different chunks", async () => {
    const messages = await collect(["event: step\r\ndata: {\"a\":1}\r", "\n\r", "\n"]);
    expect(messages).toEqual([{ event: "step", data: '{"a":1}' }]);
  });

  it("keeps a multi-byte character that is cut between two chunks", async () => {
    const bytes = encoder.encode('event: step\ndata: {"label":"Fitting the models — now"}\n\n');
    const cut = bytes.indexOf(0xe2) + 1; // inside the em dash
    const messages = await collect([bytes.slice(0, cut), bytes.slice(cut)]);
    expect(JSON.parse(messages[0]?.data ?? "").label).toBe("Fitting the models — now");
  });

  it("joins several data lines with a line feed and strips one leading space", async () => {
    const messages = await collect(["event: report\ndata: a\ndata:  b\n\n"]);
    expect(messages[0]).toEqual({ event: "report", data: "a\n b" });
  });

  it("emits a final block that has no blank line after it", async () => {
    expect(await collect(["event: report\ndata: {}"])).toEqual([{ event: "report", data: "{}" }]);
  });
});

function sseResponse(blocks: string[], init: ResponseInit = {}): Response {
  return new Response(streamOf(blocks), { status: 200, headers: { "Content-Type": "text/event-stream" }, ...init });
}
const json = (body: unknown, status: number) => Response.json(body, { status });

afterEach(() => vi.unstubAllGlobals());

function stubFetch(handler: (url: string) => Response | Promise<Response>) {
  const calls: string[] = [];
  vi.stubGlobal("fetch", (input: RequestInfo | URL) => {
    calls.push(String(input));
    return Promise.resolve(handler(String(input)));
  });
  return calls;
}

describe("streamReport", () => {
  it("reports each step and resolves with the report", async () => {
    stubFetch(() =>
      sseResponse([block("step", step(1, 2, "prices", "Downloading prices")), block("step", step(2, 2, "models", "Fitting the models")), block("report", { ticker: "SPY" })]),
    );
    const steps: ProgressStep[] = [];
    const fallback = vi.fn();
    const report = await streamReport("/api/report/SPY/stream", "/api/report/SPY", {}, { onStep: (s) => steps.push(s), onFallback: fallback });
    expect(report).toEqual({ ticker: "SPY" });
    expect(steps.map((s) => s.index)).toEqual([1, 2]);
    expect(fallback).not.toHaveBeenCalled();
  });

  it("a cached report is a report with no steps", async () => {
    stubFetch(() => sseResponse([block("report", { ticker: "SPY" })]));
    const onStep = vi.fn();
    await expect(streamReport("/s", "/p", {}, { onStep })).resolves.toEqual({ ticker: "SPY" });
    expect(onStep).not.toHaveBeenCalled();
  });

  it("an error event becomes an ApiRequestError with the message, the action and the status", async () => {
    stubFetch(() =>
      sseResponse([
        block("step", step(1, 4, "prices", "Downloading prices")),
        block("error", { code: "unknown_ticker", message: "We could not find XYZQ.", action: "Check the spelling.", status: 404 }),
      ]),
    );
    const failure = await streamReport("/s", "/p", {}).catch((e: unknown) => e);
    expect(failure).toBeInstanceOf(ApiRequestError);
    expect((failure as ApiRequestError).apiError).toMatchObject({ code: "unknown_ticker", message: "We could not find XYZQ.", action: "Check the spelling." });
    expect((failure as ApiRequestError).status).toBe(404);
  });

  it.each([404, 405])("falls back to the plain endpoint on %i", async (status) => {
    const calls = stubFetch((url) => (url.endsWith("/stream") ? json({ code: "not_found", message: "m", action: "a" }, status) : json({ ticker: "SPY" }, 200)));
    const fallback = vi.fn();
    await expect(streamReport("/api/report/SPY/stream", "/api/report/SPY", {}, { onFallback: fallback })).resolves.toEqual({ ticker: "SPY" });
    expect(calls).toEqual(["/api/report/SPY/stream", "/api/report/SPY"]);
    expect(fallback).toHaveBeenCalledOnce();
  });

  it("falls back when the network fails before the first event", async () => {
    const calls: string[] = [];
    vi.stubGlobal("fetch", (input: RequestInfo | URL) => {
      calls.push(String(input));
      return calls.length === 1 ? Promise.reject(new TypeError("Failed to fetch")) : Promise.resolve(json({ ticker: "SPY" }, 200));
    });
    await expect(streamReport("/s", "/p", {})).resolves.toEqual({ ticker: "SPY" });
    expect(calls).toEqual(["/s", "/p"]);
  });

  it("falls back when the answer is not an event stream", async () => {
    const calls = stubFetch((url) => json({ ticker: url === "/s" ? "STREAM" : "PLAIN" }, 200));
    await expect(streamReport("/s", "/p", {})).resolves.toEqual({ ticker: "PLAIN" });
    expect(calls).toEqual(["/s", "/p"]);
  });

  it("a plain JSON refusal (bad value, file too large) is an error, not a fallback", async () => {
    const calls = stubFetch(() => json({ code: "upload_too_large", message: "The file is over 1 MB.", action: "Send a smaller file." }, 413));
    const failure = await streamReport("/s", "/p", {}).catch((e: unknown) => e);
    expect(failure).toBeInstanceOf(ApiRequestError);
    expect((failure as ApiRequestError).apiError.code).toBe("upload_too_large");
    expect((failure as ApiRequestError).status).toBe(413);
    expect(calls).toEqual(["/s"]);
  });

  it("a stream that breaks after its first event is a network error, not a second request", async () => {
    const calls = stubFetch(() => sseResponse([block("step", step(1, 4, "prices", "x"))]));
    const failure = await streamReport("/s", "/p", {}).catch((e: unknown) => e);
    expect((failure as ApiRequestError).apiError.code).toBe("network");
    expect(calls).toEqual(["/s"]);
  });

  it("sends the body and the headers of the request to the stream endpoint", async () => {
    let seen: RequestInit | undefined;
    vi.stubGlobal("fetch", (_input: RequestInfo | URL, init?: RequestInit) => {
      seen = init;
      return Promise.resolve(sseResponse([block("report", { ticker: "P" })]));
    });
    await streamReport("/api/report/portfolio/stream", "/api/report/portfolio", { method: "POST", json: { name: "x" } });
    expect(seen?.method).toBe("POST");
    expect(seen?.body).toBe('{"name":"x"}');
    expect((seen?.headers as Record<string, string>)["Accept"]).toBe("text/event-stream");
  });
});

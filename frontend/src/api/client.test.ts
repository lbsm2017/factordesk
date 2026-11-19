import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiRequestError, apiRequest, apiUrl, NETWORK_ERROR } from "./client";

function respond(status: number, body: unknown): Response {
  return new Response(typeof body === "string" ? body : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => vi.unstubAllGlobals());

describe("apiUrl", () => {
  it("drops empty values and encodes the rest", () => {
    expect(apiUrl("/api/x", { a: "1", b: undefined, c: "", d: null, e: "a b" })).toBe("/api/x?a=1&e=a+b");
    expect(apiUrl("/api/x")).toBe("/api/x");
  });
});

describe("apiRequest", () => {
  it("sends a JSON body with the JSON content type", async () => {
    const fetchMock = vi.fn().mockResolvedValue(respond(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await apiRequest("/api/report/portfolio", { method: "POST", json: { tree: { name: "A" }, cost_bps: 10 } });
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(init.body).toBe('{"tree":{"name":"A"},"cost_bps":10}');
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
  });

  it("returns the parsed body on 200", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respond(200, { status: "ok" })));
    await expect(apiRequest("/api/health")).resolves.toEqual({ status: "ok" });
  });

  it("turns an ApiError body into an ApiRequestError that holds it", async () => {
    const body = {
      code: "unknown_ticker",
      message: "No prices were returned for XYZ.",
      action: "Check the ticker symbol.",
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respond(404, body)));
    const error = await apiRequest("/api/report/XYZ").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiRequestError);
    expect((error as ApiRequestError).apiError).toEqual(body);
    expect((error as ApiRequestError).status).toBe(404);
  });

  it("turns a response that is not an ApiError into an internal error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respond(500, "<html>boom</html>")));
    const error = (await apiRequest("/api/x").catch((e: unknown) => e)) as ApiRequestError;
    expect(error.apiError.code).toBe("internal");
    expect(error.apiError.message).toContain("500");
  });

  it("turns a missing response into the network error of DB6.2", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const error = (await apiRequest("/api/x").catch((e: unknown) => e)) as ApiRequestError;
    expect(error.apiError).toEqual(NETWORK_ERROR);
    expect(NETWORK_ERROR.message).toBe("The factordesk server did not answer.");
    expect(NETWORK_ERROR.action).toBe("Check that 'factordesk serve' is running, then try again.");
  });

  it("lets an abort through unchanged", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new DOMException("aborted", "AbortError")));
    const error = await apiRequest("/api/x").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(DOMException);
  });
});

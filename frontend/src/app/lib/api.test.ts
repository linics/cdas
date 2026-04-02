import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  downloadAuthenticatedFile,
  normalizeAttachmentUrl,
  setToken,
  type SubmissionAttachment,
} from "./api";

const originalFetch = globalThis.fetch;
const originalWindow = globalThis.window;
const originalDocument = globalThis.document;
const originalURL = globalThis.URL;
const originalLocalStorage = globalThis.localStorage;

describe("submission attachment api helpers", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_API_BASE_URL", "https://backend.example.com");
    const storage = new Map<string, string>();
    const localStorageMock = {
      getItem: (key: string) => storage.get(key) ?? null,
      setItem: (key: string, value: string) => {
        storage.set(key, value);
      },
      removeItem: (key: string) => {
        storage.delete(key);
      },
    };
    Object.defineProperty(globalThis, "localStorage", {
      configurable: true,
      value: localStorageMock,
    });
    Object.defineProperty(globalThis, "window", {
      configurable: true,
      value: {
        setTimeout,
        clearTimeout,
        dispatchEvent: vi.fn(),
      },
    });
  });

  afterEach(() => {
    Object.defineProperty(globalThis, "fetch", {
      configurable: true,
      value: originalFetch,
    });
    Object.defineProperty(globalThis, "window", {
      configurable: true,
      value: originalWindow,
    });
    Object.defineProperty(globalThis, "document", {
      configurable: true,
      value: originalDocument,
    });
    Object.defineProperty(globalThis, "URL", {
      configurable: true,
      value: originalURL,
    });
    Object.defineProperty(globalThis, "localStorage", {
      configurable: true,
      value: originalLocalStorage,
    });
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("maps relative upload urls to the configured backend origin", () => {
    expect(normalizeAttachmentUrl("/api/v2/submissions/8/attachments/3/download")).toBe(
      "https://backend.example.com/api/v2/submissions/8/attachments/3/download",
    );
  });

  it("keeps absolute attachment urls unchanged", () => {
    expect(normalizeAttachmentUrl("https://cdn.example.com/files/report.pdf")).toBe(
      "https://cdn.example.com/files/report.pdf",
    );
  });

  it("downloads uploaded attachments with bearer auth", async () => {
    const click = vi.fn();
    const remove = vi.fn();
    const append = vi.fn();
    const anchor = {
      click,
      remove,
      href: "",
      download: "",
    };
    const createObjectURL = vi.fn(() => "blob:attachment");
    const revokeObjectURL = vi.fn();

    Object.defineProperty(globalThis, "document", {
      configurable: true,
      value: {
        body: { appendChild: append },
        createElement: vi.fn(() => anchor),
      },
    });
    Object.defineProperty(globalThis, "URL", {
      configurable: true,
      value: {
        createObjectURL,
        revokeObjectURL,
      },
    });

    const blob = new Blob(["附件内容"], { type: "text/plain" });
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      new Response(blob, {
        status: 200,
        headers: {
          "content-disposition": 'attachment; filename="analysis.txt"',
          "content-type": "text/plain",
        },
      }),
    );
    Object.defineProperty(globalThis, "fetch", {
      configurable: true,
      value: fetchMock,
    });

    setToken("token-123");
    const attachment: SubmissionAttachment = {
      filename: "analysis.txt",
      url: "/api/v2/submissions/8/attachments/3/download",
      type: "txt",
      source: "upload",
    };

    await downloadAuthenticatedFile(attachment.url, attachment.filename);

    expect(fetchMock).toHaveBeenCalledWith(
      "https://backend.example.com/api/v2/submissions/8/attachments/3/download",
      expect.objectContaining({
        headers: expect.any(Headers),
      }),
    );
    const headers = fetchMock.mock.calls[0]?.[1]?.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer token-123");
    expect(anchor.download).toBe("analysis.txt");
    expect(anchor.href).toBe("blob:attachment");
    expect(append).toHaveBeenCalledWith(anchor);
    expect(click).toHaveBeenCalled();
    expect(remove).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:attachment");
  });
});

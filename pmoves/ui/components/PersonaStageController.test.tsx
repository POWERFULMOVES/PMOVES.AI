import { render, cleanup, act, waitFor } from "@testing-library/react";
import { PersonaStageController } from "./PersonaStageController";

// Hermetic config: PersonaStageController reads defaults from @/config, whose real
// module requires Supabase env vars at import time. Stub it so the test needs no env.
jest.mock("@/config", () => ({
  uiConfig: {
    botzGatewayUrl: "http://localhost:8054",
    showtimeUrl: "http://localhost:9225",
  },
}));

// --- Hermetic stubs (mirror the design engine's own test doubles). ---

// A fake EventSource that captures the live instance and its named listeners so a
// test can synthetically emit a Showtime frame. No real network/SSE is opened.
class FakeEventSource {
  static instances: FakeEventSource[] = [];
  url: string;
  listeners: Record<string, Array<(e: any) => void>> = {};
  onmessage: ((e: any) => void) | null = null;
  onerror: ((e: any) => void) | null = null;
  closed = false;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, cb: (e: any) => void) {
    (this.listeners[type] ||= []).push(cb);
  }

  // Test helper: dispatch a named event to registered listeners.
  emit(type: string, event: any) {
    (this.listeners[type] || []).forEach((cb) => cb(event));
  }

  close() {
    this.closed = true;
  }
}

// A fake fetch returning a gateway theme object (color -> --pm-accent).
const makeFetchImpl = () =>
  jest.fn(async () => ({
    ok: true,
    status: 200,
    json: async () => ({ color: "#00FFCC", accent: "#5EEAD4" }),
  })) as unknown as typeof fetch;

const resetRoot = () => {
  const root = document.documentElement;
  root.removeAttribute("style");
  delete root.dataset.stage;
};

beforeEach(() => {
  FakeEventSource.instances.length = 0;
  resetRoot();
});

afterEach(() => {
  cleanup();
  resetRoot();
});

describe("PersonaStageController", () => {
  it("applies the persona accent overlay from ?agent= and never touches --pm-signature", async () => {
    const fetchImpl = makeFetchImpl();

    await act(async () => {
      render(
        <PersonaStageController
          search="?agent=4090-claude"
          fetchImpl={fetchImpl}
          eventSourceImpl={FakeEventSource}
        />,
      );
    });

    const root = document.documentElement;
    await waitFor(() => {
      expect(root.style.getPropertyValue("--pm-accent")).toBe("#00FFCC");
    });
    // The reserved signature accent must remain untouched.
    expect(root.style.getPropertyValue("--pm-signature")).toBe("");
  });

  it("flips the stage to live and calls onLive(true) on a Showtime frame", async () => {
    const onLive = jest.fn();

    await act(async () => {
      render(
        <PersonaStageController
          search=""
          fetchImpl={makeFetchImpl()}
          eventSourceImpl={FakeEventSource}
          onLive={onLive}
        />,
      );
    });

    const es = FakeEventSource.instances[0];
    expect(es).toBeDefined();

    act(() => {
      es.emit("showtime.all_green.v1", {
        data: JSON.stringify({ state: "showtime" }),
      });
    });

    expect(document.documentElement.dataset.stage).toBe("live");
    expect(onLive).toHaveBeenCalledWith(true);
  });

  it("closes the EventSource on unmount", async () => {
    let unmount: () => void = () => {};
    await act(async () => {
      const result = render(
        <PersonaStageController
          search=""
          fetchImpl={makeFetchImpl()}
          eventSourceImpl={FakeEventSource}
        />,
      );
      unmount = result.unmount;
    });

    const es = FakeEventSource.instances[0];
    expect(es.closed).toBe(false);

    act(() => {
      unmount();
    });

    expect(es.closed).toBe(true);
  });
});

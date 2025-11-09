import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import UploadEventsTable from "../components/UploadEventsTable";

const trackUiMetric = jest.fn();
const trackUiEvent = jest.fn();

jest.mock("../lib/metrics", () => ({
  trackUiMetric: (...args: unknown[]) => trackUiMetric(...args),
  trackUiEvent: (...args: unknown[]) => trackUiEvent(...args),
}));

// React 19 prints a noisy act() warning in Jest even with the env flag; filter it for this suite only.
const actWarningPattern = /The current testing environment is not configured to support act/;
let consoleErrorSpy: jest.SpyInstance | undefined;
const originalConsoleError = console.error;

beforeAll(() => {
  consoleErrorSpy = jest.spyOn(console, "error").mockImplementation((...args: Parameters<typeof console.error>) => {
    const [message] = args;
    if (typeof message === "string" && actWarningPattern.test(message)) {
      return;
    }
    originalConsoleError.apply(console, args);
  });
});

afterAll(() => {
  consoleErrorSpy?.mockRestore();
  consoleErrorSpy = undefined;
});

type UploadRow = ReturnType<typeof buildRowBase>;

const buildRow = (overrides: Partial<UploadRow> = {}): UploadRow => ({
  ...buildRowBase(),
  ...overrides,
});

const buildRowBase = () => ({
  id: 42,
  upload_id: "upload-42",
  filename: "diagram.png",
  bucket: "documents",
  object_key: "owner/diagram.png",
  status: "complete",
  progress: 100,
  error_message: null,
  size_bytes: 2048,
  content_type: "image/png",
  meta: { ingest: "ui-dropzone" },
  created_at: new Date("2024-04-08T12:00:00Z").toISOString(),
  updated_at: new Date("2024-04-08T12:10:00Z").toISOString(),
  owner_id: "owner-abc",
});

let fetchResult: { data: UploadRow[]; error: { message: string } | null };
let deleteError: { message: string } | null;
let clearSmokeError: { message: string } | null;

const mockSupabase = {
  from: jest.fn(() => ({
    select: jest.fn(() => ({
      eq: jest.fn(() => ({
        order: jest.fn(() => ({
          limit: jest.fn(() => Promise.resolve(fetchResult)),
        })),
      })),
    })),
    delete: jest.fn(() => ({
      eq: jest.fn((column: string) => {
        if (column === "id") {
          return Promise.resolve({ error: deleteError });
        }
        return {
          contains: jest.fn(() => Promise.resolve({ error: clearSmokeError })),
        };
      }),
    })),
  })),
  channel: jest.fn(() => ({
    on: jest.fn().mockReturnThis(),
    subscribe: jest.fn().mockReturnValue({ data: {} }),
    unsubscribe: jest.fn(),
  })),
};

jest.mock("../lib/supabaseBrowser", () => ({
  getBrowserSupabaseClient: () => mockSupabase,
}));

const ownerId = "owner-abc";

const resetState = () => {
  fetchResult = { data: [buildRow()], error: null };
  deleteError = null;
  clearSmokeError = null;
  jest.clearAllMocks();
};

const renderTable = async (props: Parameters<typeof UploadEventsTable>[0]) => {
  await act(async () => {
    render(<UploadEventsTable {...props} />);
  });
};

beforeEach(() => {
  resetState();
});


describe("UploadEventsTable", () => {
  it("renders fetch results and logs success metric", async () => {
    await renderTable({ ownerId, limit: 5 });

    await waitFor(() => expect(screen.getByText("diagram.png")).toBeInTheDocument());

    expect(trackUiMetric).toHaveBeenCalledWith(
      "uploadEvents.fetch.success",
      expect.objectContaining({ ownerId, count: 1, durationMs: expect.any(Number) })
    );
  });

  it("emits fetch error metric when supabase fails", async () => {
    fetchResult = { data: [], error: { message: "boom" } };
    await renderTable({ ownerId });

    await waitFor(() => expect(screen.getByText("boom")).toBeInTheDocument());

    expect(trackUiMetric).toHaveBeenCalledWith(
      "uploadEvents.fetch.error",
      expect.objectContaining({ ownerId, message: "boom", durationMs: expect.any(Number) })
    );
  });

  it("logs delete metrics for success and refetches rows", async () => {
    const user = userEvent.setup();
    await renderTable({ ownerId });
    await waitFor(() => expect(screen.getByText("diagram.png")).toBeInTheDocument());

    const deleteButton = screen.getByRole("button", { name: /remove/i });
    await act(async () => {
      await user.click(deleteButton);
    });

    await waitFor(() =>
      expect(trackUiMetric).toHaveBeenCalledWith(
        "uploadEvents.delete.success",
        expect.objectContaining({ ownerId, rowId: 42, durationMs: expect.any(Number) })
      )
    );

    expect(trackUiMetric).toHaveBeenCalledWith(
      "uploadEvents.fetch.success",
      expect.objectContaining({ ownerId, count: 1, durationMs: expect.any(Number) })
    );
  });

  it("logs delete errors", async () => {
    const user = userEvent.setup();
    deleteError = { message: "not allowed" };
    await renderTable({ ownerId });
    await waitFor(() => expect(screen.getByText("diagram.png")).toBeInTheDocument());

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /remove/i }));
    });

    await waitFor(() => expect(screen.getByText("not allowed")).toBeInTheDocument());

    expect(trackUiMetric).toHaveBeenCalledWith(
      "uploadEvents.delete.error",
      expect.objectContaining({ ownerId, rowId: 42, message: "not allowed", durationMs: expect.any(Number) })
    );
  });

  it("logs clear smoke metrics", async () => {
    const user = userEvent.setup();
    await renderTable({ ownerId });
    await waitFor(() => expect(screen.getByText("diagram.png")).toBeInTheDocument());

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /clear smoke/i }));
    });

    await waitFor(() =>
      expect(trackUiMetric).toHaveBeenCalledWith(
        "uploadEvents.clearSmoke.success",
        expect.objectContaining({ ownerId, durationMs: expect.any(Number) })
      )
    );
  });

  it("logs skip event when owner id missing", async () => {
    await renderTable({ ownerId: "" });

    await waitFor(() =>
      expect(trackUiEvent).toHaveBeenCalledWith("uploadEvents.fetch.skipped", { reason: "missing-owner" })
    );
  });

  it("logs clear smoke errors", async () => {
    const user = userEvent.setup();
    clearSmokeError = { message: "failed" };
    await renderTable({ ownerId });
    await waitFor(() => expect(screen.getByText("diagram.png")).toBeInTheDocument());

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /clear smoke/i }));
    });

    await waitFor(() => expect(screen.getByText("failed")).toBeInTheDocument());

    expect(trackUiMetric).toHaveBeenCalledWith(
      "uploadEvents.clearSmoke.error",
      expect.objectContaining({ ownerId, message: "failed", durationMs: expect.any(Number) })
    );
  });
});

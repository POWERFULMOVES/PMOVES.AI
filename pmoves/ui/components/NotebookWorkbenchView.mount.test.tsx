import { render, screen } from "@testing-library/react";
import { NotebookWorkbenchView } from "./NotebookWorkbenchView";

// Hermetic config: PersonaStageController (mounted by the view) reads defaults from
// @/config, whose real module requires Supabase env at import time. Stub it so the
// test needs no env.
jest.mock("@/config", () => ({
  uiConfig: {
    botzGatewayUrl: "http://localhost:8054",
    showtimeUrl: "http://localhost:9225",
  },
}));

// SkinProvider fetches a skin.json on mount — pass children through so the tree
// renders without a network dependency.
jest.mock("@/runtime/skin/SkinProvider", () => ({
  SkinProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// The Notebook data hook talks to Supabase; return an inert, empty dataset so the
// view renders its "enter a thread" empty state without any network.
jest.mock("@/runtime/notebook", () => ({
  useSupabaseViews: () => ({
    messages: [],
    views: {},
    saveNewView: jest.fn(),
    loading: false,
    error: null,
  }),
  MultiViewEditor: () => null,
  SnapshotBrowser: () => null,
  SnapshotBookmarksPro: () => null,
  SnapshotScrubber: () => null,
  GroupManager: () => null,
}));

jest.mock("@/components/DashboardNavigation", () => ({
  __esModule: true,
  default: () => <nav data-testid="dashboard-navigation" />,
}));

jest.mock("@/components/GraphitiStatusBadge", () => ({
  GraphitiStatusBadge: () => <div data-testid="graphiti-status-badge" />,
}));

// Prove the mount wiring without depending on the controller's SSE/internals.
jest.mock("@/components/PersonaStageController", () => ({
  PersonaStageController: () => <div data-testid="persona-stage-controller" />,
}));

jest.mock("@/components/LiveStageBadge", () => ({
  LiveStageBadge: ({ live }: { live?: boolean }) => (
    <div data-testid="live-stage-badge" data-live={String(Boolean(live))} />
  ),
}));

describe("NotebookWorkbenchView mount", () => {
  it("renders without throwing and mounts the PersonaStageController", () => {
    expect(() => render(<NotebookWorkbenchView />)).not.toThrow();
    expect(screen.getByTestId("persona-stage-controller")).toBeInTheDocument();
  });

  it("mounts the LiveStageBadge alongside the GraphitiStatusBadge in the header", () => {
    render(<NotebookWorkbenchView />);
    expect(screen.getByTestId("graphiti-status-badge")).toBeInTheDocument();
    expect(screen.getByTestId("live-stage-badge")).toBeInTheDocument();
  });
});

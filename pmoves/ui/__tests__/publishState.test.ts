import { describePublishState } from "../app/dashboard/publishState";

describe("describePublishState", () => {
  it("returns waiting for poller after approval before publisher metadata arrives", () => {
    expect(
      describePublishState({
        approvalStatus: "approved",
        reviewedAt: "2026-03-27T09:15:00Z",
        meta: {},
      })
    ).toEqual({
      label: "waiting for poller",
      detailLabel: "approved @",
      detailValue: "2026-03-27T09:15:00Z",
      tone: "default",
    });
  });

  it("shows approval relayed after the poller stamps handoff metadata", () => {
    expect(
      describePublishState({
        rowStatus: "publishing",
        meta: {
          publish_approval_event_sent_at: "2026-03-27T09:18:00Z",
        },
      })
    ).toEqual({
      label: "approval relayed",
      detailLabel: "approval relayed @",
      detailValue: "2026-03-27T09:18:00Z",
      tone: "default",
    });
  });

  it("shows publisher active once the publisher starts processing", () => {
    expect(
      describePublishState({
        rowStatus: "publishing",
        meta: {
          publish_started_at: "2026-03-27T09:19:00Z",
        },
      })
    ).toEqual({
      label: "publisher active",
      detailLabel: "publisher started @",
      detailValue: "2026-03-27T09:19:00Z",
      tone: "default",
    });
  });

  it("shows publish complete once a publish event is recorded", () => {
    expect(
      describePublishState({
        rowStatus: "published",
        meta: {
          publish_event_sent_at: "2026-03-27T09:20:00Z",
        },
      })
    ).toEqual({
      label: "publish complete",
      detailLabel: "published @",
      detailValue: "2026-03-27T09:20:00Z",
      tone: "success",
    });
  });

  it("treats publish completion metadata as complete even before the row status flips", () => {
    expect(
      describePublishState({
        meta: {
          publish_completed_at: "2026-03-27T09:20:00Z",
        },
      })
    ).toEqual({
      label: "publish complete",
      detailLabel: "published @",
      detailValue: "2026-03-27T09:20:00Z",
      tone: "success",
    });
  });

  it("shows publisher active when only the publish start metadata is available", () => {
    expect(
      describePublishState({
        meta: {
          publish_started_at: "2026-03-27T09:19:00Z",
        },
      })
    ).toEqual({
      label: "publisher active",
      detailLabel: "publisher started @",
      detailValue: "2026-03-27T09:19:00Z",
      tone: "default",
    });
  });

  it("surfaces retry guidance for failed publish attempts", () => {
    expect(
      describePublishState({
        rowStatus: "publish_failed",
        meta: {
          publish_failure_stage: "discord_webhook",
        },
      })
    ).toEqual({
      label: "needs retry",
      detailLabel: "failure stage:",
      detailValue: "discord_webhook",
      tone: "danger",
    });
  });
});

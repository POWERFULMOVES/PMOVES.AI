export interface PublishMetaLike {
  reviewed_at?: string | null;
  publish_started_at?: string | null;
  publish_completed_at?: string | null;
  publish_event_sent_at?: string | null;
  publish_requested_at?: string | null;
  publish_approval_event_sent_at?: string | null;
  publish_failed_at?: string | null;
  publish_failure_reason?: string | null;
  publish_failure_stage?: string | null;
}

export interface PublishStateSummary {
  label: string;
  detailLabel?: string;
  detailValue?: string | null;
  tone: "default" | "success" | "danger";
}

interface DescribePublishStateInput {
  rowStatus?: string | null;
  approvalStatus?: string | null;
  reviewedAt?: string | null;
  meta?: PublishMetaLike | null;
}

const normalize = (value?: string | null) => (value || "").trim().toLowerCase();

/**
 * Collapse publish metadata from the studio-board and videos dashboards into
 * one operator-facing state summary.
 */
export function describePublishState({
  rowStatus,
  approvalStatus,
  reviewedAt,
  meta,
}: DescribePublishStateInput): PublishStateSummary | null {
  const status = normalize(rowStatus);
  const approval = normalize(approvalStatus);
  const reviewed = reviewedAt || meta?.reviewed_at || null;
  const publishRequestedAt = meta?.publish_requested_at || null;
  const approvalRelayedAt = meta?.publish_approval_event_sent_at || null;
  const publishStartedAt = meta?.publish_started_at || null;
  const publishCompletedAt = meta?.publish_completed_at || null;
  const publishedAt = meta?.publish_event_sent_at || null;
  const publishFailedAt = meta?.publish_failed_at || null;
  const publishFailureReason = meta?.publish_failure_reason || null;
  const publishFailureStage = meta?.publish_failure_stage || null;

  if (
    publishedAt ||
    publishCompletedAt ||
    status === "published" ||
    approval === "published"
  ) {
    return {
      label: "publish complete",
      detailLabel: publishedAt || publishCompletedAt ? "published @" : undefined,
      detailValue: publishedAt || publishCompletedAt,
      tone: "success",
    };
  }

  if (
    status === "publish_failed" ||
    approval === "publish_failed" ||
    publishFailedAt ||
    publishFailureReason
  ) {
    if (publishFailedAt) {
      return {
        label: "needs retry",
        detailLabel: "failed @",
        detailValue: publishFailedAt,
        tone: "danger",
      };
    }
    if (publishFailureStage) {
      return {
        label: "needs retry",
        detailLabel: "failure stage:",
        detailValue: publishFailureStage,
        tone: "danger",
      };
    }
    if (publishFailureReason) {
      return {
        label: "needs retry",
        detailLabel: "publish failure:",
        detailValue: publishFailureReason,
        tone: "danger",
      };
    }
    return { label: "needs retry", tone: "danger" };
  }

  if (status === "publishing" || publishStartedAt) {
    if (publishStartedAt) {
      return {
        label: "publisher active",
        detailLabel: "publisher started @",
        detailValue: publishStartedAt,
        tone: "default",
      };
    }
    if (approvalRelayedAt) {
      return {
        label: "approval relayed",
        detailLabel: "approval relayed @",
        detailValue: approvalRelayedAt,
        tone: "default",
      };
    }
    if (publishRequestedAt) {
      return {
        label: "publish requested",
        detailLabel: "publish requested @",
        detailValue: publishRequestedAt,
        tone: "default",
      };
    }
    return { label: "publishing", tone: "default" };
  }

  if (
    status === "approved" ||
    approval === "approved" ||
    approvalRelayedAt ||
    publishRequestedAt ||
    reviewed
  ) {
    if (approvalRelayedAt) {
      return {
        label: "approval relayed",
        detailLabel: "approval relayed @",
        detailValue: approvalRelayedAt,
        tone: "default",
      };
    }
    if (publishRequestedAt) {
      return {
        label: "publish requested",
        detailLabel: "publish requested @",
        detailValue: publishRequestedAt,
        tone: "default",
      };
    }
    if (reviewed) {
      return {
        label: "waiting for poller",
        detailLabel: "approved @",
        detailValue: reviewed,
        tone: "default",
      };
    }
    return { label: "approved", tone: "default" };
  }

  return null;
}

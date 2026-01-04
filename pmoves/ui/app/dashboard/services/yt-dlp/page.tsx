"use client";
import DashboardNavigation from "../../../../components/DashboardNavigation";
import YtDlpStatus from "../../tiles/YtDlpStatus";

export default function YtDlpServicePage() {
  return (
    <div className="p-6 space-y-6">
      <DashboardNavigation active="services" />
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold">yt-dlp Status</h1>
        <p className="text-sm text-neutral-600">Live status pulled from PMOVES.YT.</p>
      </header>
      <YtDlpStatus />
    </div>
  );
}


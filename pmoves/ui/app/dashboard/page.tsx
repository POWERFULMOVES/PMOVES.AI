"use client";

import { redirect } from "next/navigation";
import { useEffect } from "react";

/**
 * Dashboard root page - redirects to services overview
 */
export default function DashboardPage() {
  useEffect(() => {
    // Client-side redirect to services dashboard
    window.location.href = "/dashboard/services";
  }, []);

  // Fallback for server-side or while redirecting
  redirect("/dashboard/services");
}

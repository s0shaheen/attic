"use client";

import { useAuth } from "@/lib/auth-context";
import { useEffect, useState } from "react";

const isDev = process.env.NEXT_PUBLIC_ENVIRONMENT === "development";
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type ServiceStatus = "configured" | "fake" | "missing" | "inline";

interface DevStatus {
  environment: string;
  services: Record<string, ServiceStatus>;
}

const statusColors: Record<ServiceStatus, string> = {
  configured: "text-green-400",
  fake: "text-amber-400",
  missing: "text-red-400",
  inline: "text-blue-400",
};

const statusLabels: Record<ServiceStatus, string> = {
  configured: "OK",
  fake: "fake",
  missing: "off",
  inline: "inline",
};

export function DevBanner() {
  const { user } = useAuth();
  const [status, setStatus] = useState<DevStatus | null>(null);

  useEffect(() => {
    if (!isDev) return;
    fetch(`${API_URL}/api/dev-status`)
      .then((r) => r.json())
      .then(setStatus)
      .catch(() => {});
  }, []);

  if (!isDev) return null;

  return (
    <div className="flex items-center justify-center gap-2 bg-amber-900/40 px-4 py-1 text-xs text-amber-300">
      <span className="font-medium">Dev mode</span>
      {user?.email && (
        <>
          <span className="text-amber-500">&middot;</span>
          <span>{user.email}</span>
        </>
      )}
      {status?.services && (
        <>
          <span className="text-amber-500">&middot;</span>
          {["apify", "openai", "anthropic", "sqs"].map((svc) => {
            const s = status.services[svc] as ServiceStatus;
            return (
              <span key={svc} className={statusColors[s] || "text-neutral-400"}>
                {svc}:{statusLabels[s] || s}
              </span>
            );
          })}
        </>
      )}
    </div>
  );
}

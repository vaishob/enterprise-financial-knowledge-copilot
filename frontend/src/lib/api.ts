import type { Role } from "./types";
export const demoAuth = process.env.NEXT_PUBLIC_DEMO_AUTH !== "false";
export async function api<T>(path: string, role: Role, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init, cache: "no-store", credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(demoAuth ? {"X-Demo-Role": role} : {}), ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const message = typeof body?.detail === "string" ? body.detail : `Request failed (${response.status}). Check the backend connection and your access.`;
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}
export function humanize(value: string) { return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()); }
export function number(value: unknown, digits = 0) { return typeof value === "number" && Number.isFinite(value) ? value.toLocaleString("en-US", {maximumFractionDigits: digits}) : "—"; }
export function percent(value: number | null | undefined) { return typeof value === "number" ? `${number(value * 100, 1)}%` : "Not scored"; }

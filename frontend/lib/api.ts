/**
 * Base URL for the AEIP backend.
 *
 * Override with NEXT_PUBLIC_API_BASE_URL when the backend is not on :8000
 * (for example when another service already owns that port).
 */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/** Build a full backend URL from an /api/v1-relative path. */
export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

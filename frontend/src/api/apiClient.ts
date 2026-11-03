const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "/api/v1"
  // Loopback refers to the visitor's computer when using a public tunnel.
  // Vite already proxies these requests to the local Django service.
).replace(/^https?:\/\/(?:localhost|127\.0\.0\.1|\[::1\])(?::\d+)?(?=\/|$)/i, "")
  .replace(/\/+$/, "");

function apiUrl(path: string): string {
  return `${API_BASE_URL}/${path.replace(/^\/+/, "")}`;
}

type CsrfResponse = {
  csrfToken: string;
};

type ApiRequestOptions = RequestInit & { timeoutMs?: number };

async function requestJson<T>(
  url: string,
  options: RequestInit,
  timeoutMs: number,
  timeoutMessage: string
): Promise<T> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  const timer = setTimeout(abort, timeoutMs);
  options.signal?.addEventListener("abort", abort, { once: true });
  if (options.signal?.aborted) abort();

  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    if (response.status === 204) return undefined as T;

    const body = await response.json().catch(() => null);
    if (controller.signal.aborted) throw new Error(timeoutMessage);
    if (!response.ok) {
      const message = body?.message || body?.detail || body?.error ||
        `Request failed with status ${response.status}`;
      throw new Error(typeof message === "string" ? message : JSON.stringify(message));
    }
    if (body == null) throw new Error("The backend returned an invalid response. Check the connection and sign in again.");
    return body as T;
  } catch (error) {
    if (controller.signal.aborted && !options.signal?.aborted) throw new Error(timeoutMessage);
    throw error;
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener("abort", abort);
  }
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {}
): Promise<T> {
  const { timeoutMs = 30000, ...requestOptions } = options;
  const headers = new Headers(options.headers);
  const method = (options.method || "GET").toUpperCase();

  if (options.body instanceof FormData) {
    headers.delete("Content-Type");
  } else if (options.body != null && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  // Django requires the current CSRF token for unsafe requests.
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrfData = await requestJson<CsrfResponse>(apiUrl("/auth/csrf/"), {
      credentials: "include", cache: "no-store", signal: options.signal,
    }, 15000, "Could not prepare the request within 15 seconds. Check your connection and sign in again. The request has not been sent.");

    headers.set("X-CSRFToken", csrfData.csrfToken);
  }

  return requestJson<T>(apiUrl(path), {
    ...requestOptions,
    method,
    credentials: "include",
    headers,
  }, timeoutMs, method === "POST" && path === "/billing-records/upload/"
    ? "Upload confirmation timed out. The file may already be saved. Check the Dashboard before uploading again."
    : "The backend did not respond in time. Check your connection. If you were saving changes, refresh the record to verify whether they were saved.");
}

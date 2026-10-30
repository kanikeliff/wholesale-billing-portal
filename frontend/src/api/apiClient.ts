const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "/api/v1"
).replace(/\/+$/, "");

function apiUrl(path: string): string {
  return `${API_BASE_URL}/${path.replace(/^\/+/, "")}`;
}

type CsrfResponse = {
  csrfToken: string;
};

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const headers = new Headers(options.headers);
  const method = (options.method || "GET").toUpperCase();

  if (options.body instanceof FormData) {
    headers.delete("Content-Type");
  } else if (options.body != null && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  // Django requires the current CSRF token for unsafe requests.
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrfResponse = await fetch(apiUrl("/auth/csrf/"), {
      credentials: "include",
    });

    if (!csrfResponse.ok) {
      throw new Error("Unable to obtain CSRF token.");
    }

    const csrfData =
      (await csrfResponse.json()) as CsrfResponse;

    headers.set("X-CSRFToken", csrfData.csrfToken);
  }

  const response = await fetch(apiUrl(path), {
    ...options,
    method,
    credentials: "include",
    headers,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);

    const message =
      errorBody?.message ||
      errorBody?.detail ||
      errorBody?.error ||
      `Request failed with status ${response.status}`;

    throw new Error(
      typeof message === "string"
        ? message
        : JSON.stringify(message)
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

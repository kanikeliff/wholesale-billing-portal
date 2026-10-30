import { apiRequest } from "./apiClient";

export interface AuthUser {
  id: number;
  username: string;
}

interface AuthResponse {
  authenticated: boolean;
  user: AuthUser;
}

export function loginUser(
  username: string,
  password: string
): Promise<AuthResponse> {
  return apiRequest<AuthResponse>("/auth/login/", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function getCurrentUser(): Promise<AuthResponse> {
  return apiRequest<AuthResponse>("/auth/me/");
}

export function logoutUser(): Promise<{
  authenticated: boolean;
}> {
  return apiRequest("/auth/logout/", {
    method: "POST",
  });
}
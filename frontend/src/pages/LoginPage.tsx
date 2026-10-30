import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import {
  getCurrentUser,
  loginUser,
  type AuthUser,
} from "../api/authApi";

interface LoginPageProps {
  onAuthenticated: (user: AuthUser) => void;
}

export default function LoginPage({
  onAuthenticated,
}: LoginPageProps) {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loggingIn, setLoggingIn] = useState(false);

  useEffect(() => {
    let active = true;

    getCurrentUser()
      .then((result) => {
        if (!active) return;

        onAuthenticated(result.user);
        navigate("/dashboard", { replace: true });
      })
      .catch(() => {
        // No active session: remain on the login page.
      });

    return () => {
      active = false;
    };
  }, [navigate, onAuthenticated]);

  const handleLogin = async (
    event: FormEvent<HTMLFormElement>
  ) => {
    event.preventDefault();
    if (loggingIn) return;

    setError("");
    setLoggingIn(true);

    try {
      const result = await loginUser(
        email.trim(),
        password
      );

      onAuthenticated(result.user);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Login failed. Please try again."
      );
    } finally {
      setLoggingIn(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        fontFamily: "Arial, sans-serif",
        backgroundColor: "#ffffff",
        padding: "20px",
        boxSizing: "border-box",
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: "420px",
          border: "1px solid #444",
          borderRadius: "12px",
          padding: "34px",
          backgroundColor: "#ffffff",
          boxSizing: "border-box",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            marginBottom: "24px",
          }}
        >
          <img
            src="/mirabito-new-logo.png"
            alt="Mirabito Logo"
            style={{
              width: "280px",
              maxWidth: "100%",
              height: "auto",
              display: "block",
            }}
          />
        </div>

        <h1
          style={{
            marginTop: 0,
            marginBottom: "6px",
            color: "#111111",
            fontSize: "30px",
          }}
        >
          Mirabito Portal
        </h1>

        <h2
          style={{
            color: "#111111",
            marginTop: 0,
            marginBottom: "28px",
            fontSize: "24px",
            fontWeight: "normal",
          }}
        >
          Login
        </h2>

        <form onSubmit={handleLogin}>
          <div
            style={{
              marginBottom: "18px",
            }}
          >
            <label
              htmlFor="email"
              style={{
                display: "block",
                color: "#111111",
                marginBottom: "8px",
                fontWeight: "bold",
                fontSize: "16px",
              }}
            >
              Username
            </label>

            <input
              id="email"
              type="text"
              value={email}
              onChange={(event) => {
                setEmail(event.target.value);
                setError("");
              }}
              placeholder="Enter your username"
              required
              autoComplete="username"
              style={{
                width: "100%",
                padding: "12px",
                boxSizing: "border-box",
                backgroundColor: "#ffffff",
                color: "#111111",
                border: "1px solid #888888",
                borderRadius: "6px",
                fontSize: "15px",
              }}
            />
          </div>

          <div
            style={{
              marginBottom: "22px",
            }}
          >
            <label
              htmlFor="password"
              style={{
                display: "block",
                color: "#111111",
                marginBottom: "8px",
                fontWeight: "bold",
                fontSize: "16px",
              }}
            >
              Password
            </label>

            <input
              id="password"
              type="password"
              value={password}
              onChange={(event) => {
                setPassword(event.target.value);
                setError("");
              }}
              placeholder="Enter your password"
              required
              autoComplete="current-password"
              style={{
                width: "100%",
                padding: "12px",
                boxSizing: "border-box",
                backgroundColor: "#ffffff",
                color: "#111111",
                border: "1px solid #888888",
                borderRadius: "6px",
                fontSize: "15px",
              }}
            />
          </div>

          {error && (
            <div
              style={{
                color: "#b42318",
                backgroundColor: "#fff1f1",
                border: "1px solid #e6a5a5",
                borderRadius: "6px",
                padding: "10px",
                marginBottom: "18px",
                fontWeight: "bold",
                fontSize: "14px",
              }}
            >
              {error}
            </div>
          )}
          <button
          type="submit"
          disabled={loggingIn}
          style={{
          width: "100%",
          padding: "13px",
          cursor: loggingIn ? "wait" : "pointer",
          backgroundColor: "#222222",
          color: "#ffffff",
          border: "none",
          borderRadius: "6px",
          fontSize: "17px",
          }}
          >
          {loggingIn ? "Signing in..." : "Login"}
          </button>

        </form>

        <p
          style={{
            marginTop: "20px",
            marginBottom: 0,
            color: "#666666",
            fontSize: "14px",
            textAlign: "center",
          }}
        >
          Secure sign-in using your Mirabito development account.
        </p>
      </div>
    </div>
  );
}
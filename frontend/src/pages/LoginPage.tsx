import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

export default function LoginPage() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const DEMO_EMAIL = "cansar2002@gmail.com";
  const DEMO_PASSWORD = "CanCan02";

  useEffect(() => {
    const isAuthenticated =
      localStorage.getItem("isAuthenticated") === "true";

    if (isAuthenticated) {
      navigate("/dashboard", { replace: true });
    }
  }, [navigate]);

  const handleLogin = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    setError("");

    if (
      email === DEMO_EMAIL &&
      password === DEMO_PASSWORD
    ) {
      localStorage.setItem("isAuthenticated", "true");

      navigate("/dashboard", {
        replace: true,
      });
    } else {
      setError("Invalid email or password.");
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
            src="/mirabito-logo.jpg"
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
              Email
            </label>

            <input
              id="email"
              type="email"
              value={email}
              onChange={(event) => {
                setEmail(event.target.value);
                setError("");
              }}
              placeholder="Enter your email"
              required
              autoComplete="email"
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
            style={{
              width: "100%",
              padding: "13px",
              cursor: "pointer",
              backgroundColor: "#222222",
              color: "#ffffff",
              border: "none",
              borderRadius: "6px",
              fontSize: "17px",
            }}
          >
            Login
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
          Demo authentication for frontend development.
        </p>
      </div>
    </div>
  );
}
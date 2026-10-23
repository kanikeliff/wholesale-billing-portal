import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  getBillingRecords,
  type BillingRecordSummary,
} from "../api/billingRecordApi";

const theme = {
  background: "#f4f6f9",
  surface: "#ffffff",
  border: "#e2e6ed",
  text: "#202938",
  muted: "#667085",
  brand: "#b21f36",
};

export default function DashboardPage() {
  const navigate = useNavigate();
  const [records, setRecords] = useState<BillingRecordSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadRecords = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await getBillingRecords();
      if (!Array.isArray(response.records)) {
        throw new Error("Unexpected billing records response.");
      }
      setRecords(response.records);
    } catch (err) {
      setRecords([]);
      setError(
        err instanceof Error ? err.message : "Unable to load billing records."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadRecords();
  }, [loadRecords]);

  const handleLogout = () => {
    localStorage.removeItem("isAuthenticated");
    navigate("/login");
  };

  const buttonStyle = {
    padding: "11px 17px",
    borderRadius: "8px",
    border: `1px solid ${theme.brand}`,
    background: theme.brand,
    color: "#ffffff",
    fontWeight: 600,
    cursor: "pointer",
    textDecoration: "none",
    display: "inline-block",
  } as const;

  return (
    <main style={{ minHeight: "100vh", padding: "28px", background: theme.background, color: theme.text, textAlign: "left" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "18px", flexWrap: "wrap", padding: "24px", background: theme.surface, border: `1px solid ${theme.border}`, borderRadius: "12px" }}>
        <div>
          <h1 style={{ margin: "0 0 8px", fontSize: "28px", color: theme.text }}>Wholesale Billing Portal</h1>
          <p style={{ margin: 0, color: theme.muted }}>Review and manage BOL records</p>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "10px" }}>
          <Link to="/upload" style={buttonStyle}>Upload BOL</Link>
          <button type="button" onClick={handleLogout} style={{ ...buttonStyle, color: theme.text, background: "white", borderColor: theme.border }}>Logout</button>
        </div>
      </header>

      <section style={{ marginTop: "24px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px", flexWrap: "wrap" }}>
          <div>
            <h2 style={{ margin: "0 0 6px", color: theme.text }}>Billing Records</h2>
            <p style={{ margin: 0, color: theme.muted, fontSize: "13px" }}>Records retrieved from the backend API</p>
          </div>
          <button type="button" onClick={() => void loadRecords()} disabled={loading} style={{ ...buttonStyle, background: "white", color: theme.brand }}>
            Refresh Records
          </button>
        </div>

        {loading && <p role="status" style={{ marginTop: "22px" }}>Loading billing records...</p>}
        {!loading && error && (
          <div role="alert" style={{ marginTop: "20px", padding: "16px", background: "#fff4f4", color: "#a11d2f", border: "1px solid #efb6be", borderRadius: "9px" }}>
            Unable to load backend records: {error}
          </div>
        )}
        {!loading && !error && records.length === 0 && <p style={{ marginTop: "20px" }}>No billing records found.</p>}

        {!loading && !error && records.length > 0 && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 280px), 1fr))", gap: "18px", marginTop: "20px" }}>
            {records.map((bol) => (
              <article key={bol.recordId} style={{ background: theme.surface, border: `1px solid ${theme.border}`, borderRadius: "10px", padding: "20px", minWidth: 0 }}>
                <p style={{ margin: "0 0 12px", color: theme.muted, fontSize: "12px" }}>Record ID: {bol.recordId}</p>
                <h3 style={{ margin: "0 0 12px", color: theme.text, fontSize: "19px" }}>
                  { bol.fields?.bolNumber?.normalizedValue!= null ? `BOL ${bol.fields?.bolNumber?.normalizedValue}` : "Billing Record"}
                </h3>
                {bol.fields?.supplier?.normalizedValue && <p style={{ margin: "0 0 8px" }}><strong>Supplier:</strong> {bol.fields?.supplier?.normalizedValue}</p>}
                {bol.fields?.carrier?.normalizedValue && <p style={{ margin: "0 0 8px" }}><strong>Carrier:</strong> {bol.fields?.carrier?.normalizedValue}</p>}
                <p style={{ margin: "0 0 18px" }}><strong>Status:</strong> <span style={{ color: theme.brand, fontWeight: 600 }}>{bol.status.replace(/_/g, " ")}</span></p>
                <Link to={`/records/${encodeURIComponent(bol.recordId)}/review`} style={buttonStyle}>Review Record</Link>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
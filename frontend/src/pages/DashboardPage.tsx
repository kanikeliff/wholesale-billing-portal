import { Link, useNavigate } from "react-router-dom";
import { mockBols } from "../data/mockBol";

export default function DashboardPage() {
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem("isAuthenticated");
    navigate("/login");
  };

  return (
    <div
      style={{
        padding: "32px",
        fontFamily: "Arial",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "20px",
        }}
      >
        <div>
          <h1>Wholesale Billing Portal</h1>

          <p>
            Review and manage BOL records
          </p>
        </div>

        <div
          style={{
            display: "flex",
            gap: "10px",
            alignItems: "center",
          }}
        >
          <Link to="/upload">
            <button
              style={{
                padding: "10px 16px",
                cursor: "pointer",
              }}
            >
              Upload BOL
            </button>
          </Link>

          <button
            type="button"
            onClick={handleLogout}
            style={{
              padding: "10px 16px",
              cursor: "pointer",
            }}
          >
            Logout
          </button>
        </div>
      </div>

      <hr />

      <h2>Billing Records</h2>

      <div
        style={{
          display: "grid",
          gridTemplateColumns:
            "repeat(auto-fit, minmax(280px, 1fr))",
          gap: "20px",
          marginTop: "20px",
        }}
      >
        {mockBols.map((bol) => (
          <div
            key={bol.recordId}
            style={{
              border: "1px solid #ccc",
              borderRadius: "8px",
              padding: "20px",
            }}
          >
            <p>
              <strong>BOL #:</strong>{" "}
              {bol.bolNumber}
            </p>

            <p>
              <strong>Supplier:</strong>{" "}
              {bol.supplier}
            </p>

            <p>
              <strong>Carrier:</strong>{" "}
              {bol.carrier}
            </p>

            <p>
              <strong>Status:</strong>{" "}
              {bol.status}
            </p>

            <Link
              to={`/records/${bol.recordId}/review`}
            >
              <button
                style={{
                  padding: "8px 14px",
                  cursor: "pointer",
                }}
              >
                Review Record
              </button>
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from "react-router-dom";

import DashboardPage from "./pages/DashboardPage";
import UploadPage from "./pages/UploadPage";
import ReviewPage from "./pages/ReviewPage";
import LoginPage from "./pages/LoginPage";

function ProtectedRoute({
  children,
}: {
  children: React.ReactNode;
}) {
  const isAuthenticated =
    localStorage.getItem("isAuthenticated") === "true";

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={<Navigate to="/dashboard" replace />}
        />

        <Route
          path="/login"
          element={<LoginPage />}
        />

        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/upload"
          element={
            <ProtectedRoute>
              <UploadPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/records/:id/review"
          element={
            <ProtectedRoute>
              <ReviewPage />
            </ProtectedRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;



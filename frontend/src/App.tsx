import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from "react-router-dom";

import {
  useCallback,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import DashboardPage from "./pages/DashboardPage";
import UploadPage from "./pages/UploadPage";
import ReviewPage from "./pages/ReviewPage";
import LoginPage from "./pages/LoginPage";

import {
  getCurrentUser,
  type AuthUser,
} from "./api/authApi";

function ProtectedRoute({
  children,
  user,
  loading,
}: {
  children: ReactNode;
  user: AuthUser | null;
  loading: boolean;
}) {
  if (loading) {
    return <div style={{ padding: 24 }}>Checking session...</div>;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}

function App() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const handleAuthenticated = useCallback(
    (authenticatedUser: AuthUser) => {
      setUser(authenticatedUser);
    },
    []
  );

  useEffect(() => {
    let active = true;

    getCurrentUser()
      .then((result) => {
        if (active) setUser(result.user);
      })
      .catch(() => {
        if (active) setUser(null);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={<Navigate to="/dashboard" replace />}
        />

        <Route
          path="/login"
          element={
            <LoginPage
              onAuthenticated={handleAuthenticated}
            />
          }
        />

        <Route
          path="/dashboard"
          element={
            <ProtectedRoute user={user} loading={loading}>
              <DashboardPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/upload"
          element={
            <ProtectedRoute user={user} loading={loading}>
              <UploadPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/records/:id/review"
          element={
            <ProtectedRoute user={user} loading={loading}>
              <ReviewPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="*"
          element={<Navigate to="/dashboard" replace />}
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;




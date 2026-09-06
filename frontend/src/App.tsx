import { AnimatePresence } from "framer-motion";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Aurora, Toaster } from "./components/ui";
import { BootSplash } from "./components/BootSplash";
import { AppShell } from "./components/AppShell";
import { useAuth } from "./features/auth/AuthContext";
import LoginPage from "./features/auth/LoginPage";
import RegisterPage from "./features/auth/RegisterPage";
import GroupsPage from "./features/groups/GroupsPage";
import DashboardPage from "./features/groups/DashboardPage";
import MembersPage from "./features/groups/MembersPage";
import ExpensesPage from "./features/expenses/ExpensesPage";
import SettleUpPage from "./features/settlements/SettleUpPage";
import ReportsPage from "./features/reports/ReportsPage";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, ready } = useAuth();
  const location = useLocation();

  if (!ready) return <BootSplash />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}

function RedirectIfSignedIn({ children }: { children: React.ReactNode }) {
  const { user, ready } = useAuth();
  if (!ready) return <BootSplash />;
  if (user) return <Navigate to="/groups" replace />;
  return <>{children}</>;
}

export default function App() {
  const location = useLocation();

  return (
    <>
      <Aurora />
      <Toaster />
      {/* Keyed on pathname so route changes animate rather than snap. */}
      <AnimatePresence mode="wait">
        <Routes location={location} key={location.pathname}>
          <Route
            path="/login"
            element={
              <RedirectIfSignedIn>
                <LoginPage />
              </RedirectIfSignedIn>
            }
          />
          <Route
            path="/register"
            element={
              <RedirectIfSignedIn>
                <RegisterPage />
              </RedirectIfSignedIn>
            }
          />

          <Route
            element={
              <RequireAuth>
                <AppShell />
              </RequireAuth>
            }
          >
            <Route path="/groups" element={<GroupsPage />} />
            <Route path="/groups/:groupId/dashboard" element={<DashboardPage />} />
            <Route path="/groups/:groupId/expenses" element={<ExpensesPage />} />
            <Route path="/groups/:groupId/settle" element={<SettleUpPage />} />
            <Route path="/groups/:groupId/reports" element={<ReportsPage />} />
            <Route path="/groups/:groupId/members" element={<MembersPage />} />
            <Route
              path="/groups/:groupId"
              element={<Navigate to="dashboard" replace />}
            />
          </Route>

          <Route path="*" element={<Navigate to="/groups" replace />} />
        </Routes>
      </AnimatePresence>
    </>
  );
}

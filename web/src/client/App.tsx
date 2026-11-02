import { Navigate, Route, Routes } from "react-router";
import { Layout } from "./components/Layout";
import { PreferencesProvider } from "./lib/preferences";
import { SessionProvider } from "./lib/session";
import { GuidelineDetail, Guidelines } from "./pages/Guidelines";
import { AttemptView, History } from "./pages/History";
import { Home } from "./pages/Home";
import { MedicationDetail, Medications } from "./pages/Medications";
import { NotFound } from "./pages/NotFound";
import { Privacy } from "./pages/Privacy";
import { Quiz } from "./pages/Quiz";
import { Settings } from "./pages/Settings";
import { SignIn } from "./pages/SignIn";

export function App() {
  return (
    <SessionProvider>
      <PreferencesProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Home />} />
            <Route path="quiz" element={<Quiz />} />
            <Route path="history" element={<History />} />
            <Route path="history/:id" element={<AttemptView />} />
            <Route path="sign-in" element={<SignIn />} />
            <Route path="guidelines" element={<Guidelines />} />
            <Route path="guidelines/:id" element={<GuidelineDetail />} />
            <Route path="medications" element={<Medications />} />
            <Route path="medications/:id" element={<MedicationDetail />} />
            <Route path="settings" element={<Settings />} />
            <Route path="privacy" element={<Privacy />} />
            <Route path="account" element={<Navigate to="/settings" replace />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </PreferencesProvider>
    </SessionProvider>
  );
}

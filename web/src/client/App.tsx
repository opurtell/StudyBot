import { Route, Routes } from "react-router";
import { Layout } from "./components/Layout";
import { SessionProvider } from "./lib/session";
import { Account } from "./pages/Account";
import { GuidelineDetail, Guidelines } from "./pages/Guidelines";
import { Home } from "./pages/Home";
import { MedicationDetail, Medications } from "./pages/Medications";
import { NotFound } from "./pages/NotFound";
import { SignIn } from "./pages/SignIn";

export function App() {
  return (
    <SessionProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="sign-in" element={<SignIn />} />
          <Route path="guidelines" element={<Guidelines />} />
          <Route path="guidelines/:id" element={<GuidelineDetail />} />
          <Route path="medications" element={<Medications />} />
          <Route path="medications/:id" element={<MedicationDetail />} />
          <Route path="account" element={<Account />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </SessionProvider>
  );
}

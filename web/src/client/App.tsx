import { Route, Routes } from "react-router";
import { Layout } from "./components/Layout";
import { SessionProvider } from "./lib/session";
import { Account } from "./pages/Account";
import { Home } from "./pages/Home";
import { NotFound } from "./pages/NotFound";
import { SignIn } from "./pages/SignIn";

export function App() {
  return (
    <SessionProvider>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="sign-in" element={<SignIn />} />
          <Route path="account" element={<Account />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </SessionProvider>
  );
}

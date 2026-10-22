import { NavLink, Outlet, Route, Routes } from "react-router-dom";

import { Clients } from "./pages/Clients";
import { Feed } from "./pages/Feed";
import { Home } from "./pages/Home";
import { InsightPage } from "./pages/InsightPage";
import { NotFound } from "./pages/NotFound";

function Layout() {
  return (
    <>
      <header className="top">
        <nav className="nav" aria-label="Разделы">
          <NavLink to="/" end>
            Главная
          </NavLink>
          <NavLink to="/clients">Сводка</NavLink>
        </nav>
        <p className="top-note">Прототип · данные синтетические</p>
      </header>
      <main className="main">
        <Outlet />
      </main>
    </>
  );
}

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="clients" element={<Clients />} />
        <Route path="clients/:clientId" element={<Feed />} />
        <Route path="clients/:clientId/events/:eventId" element={<InsightPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}

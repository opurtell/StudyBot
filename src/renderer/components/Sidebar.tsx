import { NavLink, useNavigate } from "react-router-dom";
import { useTheme } from "../hooks/useTheme";
import { useBackgroundProcesses } from "../providers/BackgroundProcessProvider";

interface NavItem {
  icon: string;
  label: string;
  path: string;
}

const primaryNav: NavItem[] = [
  { icon: "visibility", label: "Observations", path: "/" },
  { icon: "clinical_notes", label: "Clinical Guidelines", path: "/guidelines" },
  { icon: "biotech", label: "CMG & Notes Status", path: "/library" },
  { icon: "medication", label: "Medications", path: "/medication" },
];

const secondaryNav: NavItem[] = [
  { icon: "settings", label: "Settings", path: "/settings" },
];

export default function Sidebar() {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const { activeProcesses } = useBackgroundProcesses();

  return (
    <aside className="h-screen w-64 fixed left-0 top-0 bg-surface-container-low flex flex-col py-8 z-40">
      {/* App title */}
      <div className="px-6 mb-12">
        <h1 className="font-headline text-2xl font-bold text-primary leading-tight">
          Study Assistant
        </h1>
        <p className="font-label text-[10px] uppercase tracking-[0.2em] text-on-surface-variant mt-1">
          Clinical Recall
        </p>
      </div>

      {/* Primary navigation */}
      <nav className="flex-1 space-y-2 px-4" aria-label="Primary navigation">
        {primaryNav.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 transition-all duration-200 ${
                isActive
                  ? "bg-surface-container-lowest text-primary font-bold"
                  : "text-on-surface-variant hover:text-primary hover:bg-tertiary-fixed/20"
              }`
            }
          >
            <span className="material-symbols-outlined">{item.icon}</span>
            <span className="font-label text-sm uppercase tracking-wider">
              {item.label}
            </span>
          </NavLink>
        ))}
      </nav>

      {/* Bottom section */}
      <div className="px-4 mt-auto space-y-6">
        {/* Start Session CTA */}
        <button
          onClick={() => navigate("/quiz")}
          className="w-full bg-primary text-on-primary py-4 px-4 font-label text-xs uppercase tracking-[0.2em] hover:opacity-90 transition-opacity"
        >
          Start Revision
        </button>

        {/* Background processes */}
        {activeProcesses.length > 0 && (
          <div className="space-y-2 px-4">
            {activeProcesses.map((process) => (
              <div key={process.id} className="flex items-center gap-2">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-status-caution opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-status-caution" />
                </span>
                <span className="font-mono text-[10px] text-on-surface-variant">
                  {process.label}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          className="flex items-center gap-3 px-4 w-full text-on-surface-variant hover:text-primary transition-colors"
        >
          <span className="material-symbols-outlined text-sm">
            {theme === "dark" ? "light_mode" : "dark_mode"}
          </span>
          <span className="font-label text-xs uppercase tracking-wider">
            {theme === "dark" ? "Light Mode" : "Dark Mode"}
          </span>
        </button>

        {/* Secondary nav */}
        <div className="space-y-3 pt-6 border-t border-outline-variant/15">
          {secondaryNav.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 font-label text-xs uppercase tracking-wider transition-colors ${
                  isActive
                    ? "text-primary"
                    : "text-on-surface-variant hover:text-primary"
                }`
              }
            >
              <span className="material-symbols-outlined text-sm">
                {item.icon}
              </span>
              {item.label}
            </NavLink>
          ))}
        </div>
      </div>
    </aside>
  );
}

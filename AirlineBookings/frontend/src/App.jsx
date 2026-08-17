import { useEffect, useState } from "react";
import ChatApp from "./components/ChatApp";
import { useTheme } from "./hooks/useTheme";
import { SunIcon, MoonIcon, PlaneIcon } from "./components/icons";
import { api } from "./api";

// No login screen — the app authenticates a guest session silently in the
// background so every backend call (which requires a bearer token) still
// works, but the person lands directly on the welcome message. Swap this
// for a real auth flow later without touching anything else.
async function ensureGuestSession() {
  if (sessionStorage.getItem("token")) return;
  const guestId = crypto.randomUUID().slice(0, 8);
  const { access_token } = await api.login(`guest-${guestId}@udaanaarakshan.app`, guestId);
  sessionStorage.setItem("token", access_token);
}

export default function App() {
  const { theme, toggleTheme } = useTheme();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    ensureGuestSession().finally(() => setReady(true));
  }, []);

  if (!ready) {
    return <div className="app-boot" aria-hidden="true" />;
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar__brand">
          <span className="topbar__mark">
            <PlaneIcon />
          </span>
          Udaan Aarakshan
        </div>
        <button
          className="theme-toggle"
          onClick={toggleTheme}
          aria-label={theme === "light" ? "Switch to dark theme" : "Switch to light theme"}
          title={theme === "light" ? "Switch to dark theme" : "Switch to light theme"}
        >
          {theme === "light" ? <MoonIcon /> : <SunIcon />}
        </button>
      </header>

      <ChatApp />
    </div>
  );
}

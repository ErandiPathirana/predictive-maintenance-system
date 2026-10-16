import { AppHeader } from "./components/AppHeader";
import { StatusPage } from "./pages/StatusPage";

export default function App() {
  return (
    <>
      <AppHeader />
      <main className="shell">
        <StatusPage />
      </main>
      <footer className="shell app-footer">
        Predictions are decision support for a research prototype. They are not a safety system and must not replace
        qualified engineering judgement.
      </footer>
    </>
  );
}

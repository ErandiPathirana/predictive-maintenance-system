import { lazy, Suspense } from "react";
import { HashRouter, Route, Routes } from "react-router-dom";
import { AppLayout } from "./components/AppLayout";
import { LoadingBlock } from "./components/StateViews";
import { ModelProvider } from "./context/ModelContext";
import { SessionProvider } from "./context/SessionContext";
import DashboardPage from "./pages/DashboardPage";
import HistoryPage from "./pages/HistoryPage";
import ResultsPage from "./pages/ResultsPage";
import UploadPage from "./pages/UploadPage";

// Chart and evaluation code is loaded only when those pages are opened.
const MonitoringPage = lazy(() => import("./pages/MonitoringPage"));
const EvaluationPage = lazy(() => import("./pages/EvaluationPage"));
const ResearchPage = lazy(() => import("./pages/ResearchPage"));

function NotFound() {
  return <div className="panel"><h1>Page not found</h1><p>Choose a page from the menu.</p></div>;
}

/** HashRouter keeps working on any static host without server rewrite rules. */
export default function App() {
  return (
    <ModelProvider>
      <SessionProvider>
        <HashRouter>
          <Suspense fallback={<LoadingBlock />}>
            <Routes>
              <Route element={<AppLayout />}>
                <Route index element={<DashboardPage />} />
                <Route path="monitoring" element={<MonitoringPage />} />
                <Route path="upload" element={<UploadPage />} />
                <Route path="results" element={<ResultsPage />} />
                <Route path="history" element={<HistoryPage />} />
                <Route path="evaluation" element={<EvaluationPage />} />
                <Route path="research" element={<ResearchPage />} />
                <Route path="*" element={<NotFound />} />
              </Route>
            </Routes>
          </Suspense>
        </HashRouter>
      </SessionProvider>
    </ModelProvider>
  );
}

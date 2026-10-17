import { lazy, Suspense } from "react";
import { HashRouter, Route, Routes } from "react-router-dom";
import { AppLayout } from "./components/AppLayout";
import { LoadingBlock } from "./components/StateViews";
import { ModelProvider } from "./context/ModelContext";
import { SessionProvider } from "./context/SessionContext";
import AssessmentDetailPage from "./pages/AssessmentDetailPage";
import AssessPage from "./pages/AssessPage";
import DashboardPage from "./pages/DashboardPage";
import HistoryPage from "./pages/HistoryPage";
import ResultsPage from "./pages/ResultsPage";
import UploadPage from "./pages/UploadPage";

// Chart code is loaded only when the monitoring page is opened.
const MonitoringPage = lazy(() => import("./pages/MonitoringPage"));

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
                <Route path="assess" element={<AssessPage />} />
                <Route path="assessment/:id" element={<AssessmentDetailPage />} />
                <Route path="monitoring" element={<MonitoringPage />} />
                <Route path="upload" element={<UploadPage />} />
                <Route path="results" element={<ResultsPage />} />
                <Route path="history" element={<HistoryPage />} />
                <Route path="*" element={<NotFound />} />
              </Route>
            </Routes>
          </Suspense>
        </HashRouter>
      </SessionProvider>
    </ModelProvider>
  );
}

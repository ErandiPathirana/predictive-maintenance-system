import { getHealth, getModelInfo } from "../api/client";
import { ErrorNotice } from "../components/ErrorNotice";
import { ModelDetails } from "../components/ModelDetails";
import { StatusLamp } from "../components/StatusLamp";
import { useApiResource } from "../hooks/useApiResource";

// Defined outside the component so the function identity is stable between renders.
const loadStatus = () => Promise.all([getHealth(), getModelInfo()]);

export function StatusPage() {
  const { state, reload } = useApiResource(loadStatus);

  return (
    <section aria-labelledby="status-heading">
      <h2 id="status-heading">System status</h2>
      <p className="lede">Check that the server and the trained model are ready before entering sensor readings.</p>

      <ul className="lamps">
        {state.status === "loading" && (
          <>
            <StatusLamp tone="idle" title="Server" state="Checking" />
            <StatusLamp tone="idle" title="Trained model" state="Checking" />
          </>
        )}
        {state.status === "error" && (
          <>
            <StatusLamp tone="fault" title="Server" state="Not reachable" />
            <StatusLamp tone="idle" title="Trained model" state="Unknown" />
          </>
        )}
        {state.status === "success" && (
          <>
            <StatusLamp tone="ok" title="Server" state="Running" detail={`Version ${state.data[0].app_version}`} />
            {state.data[1].model_ready ? (
              <StatusLamp tone="ok" title="Trained model" state="Ready" />
            ) : (
              <StatusLamp
                tone="warn"
                title="Trained model"
                state="Not loaded"
                detail={state.data[1].reason ?? "The server has no model to use yet."}
              />
            )}
          </>
        )}
      </ul>

      {state.status === "loading" && (
        <p className="hint">Connecting. On free hosting the first request can take up to a minute while the server wakes up.</p>
      )}
      {state.status === "error" && (
        <ErrorNotice title="Could not connect" message={state.error.message} onRetry={reload} />
      )}
      {state.status === "success" && <ModelDetails info={state.data[1]} />}
    </section>
  );
}

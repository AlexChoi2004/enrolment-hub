import { useEffect, useState } from "react";
import { type Loaded, loadDashboard } from "./api";
import { Dashboard } from "./components/Dashboard";

type State = { status: "loading" } | Loaded;

interface Props {
  endpoint: string;
  fetchImpl?: typeof fetch;
}

export function App({ endpoint, fetchImpl }: Props) {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    loadDashboard(endpoint, fetchImpl, controller.signal).then(setState, () => undefined); // an abort means the page was closed
    return () => controller.abort();
  }, [endpoint, fetchImpl]);

  if (state.status === "loading") return <p className="dash-muted" role="status" aria-live="polite">Loading your dashboard…</p>;
  if (state.status === "error") {
    return (
      <div className="dash-card dash-error" role="alert">
        <p>{state.message}</p>
        {state.loginNeeded ? <p><a href="/login">Go to the login page</a></p> : null}
      </div>
    );
  }
  return <Dashboard data={state.data} />;
}

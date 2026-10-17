import { Button } from "@mantine/core";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, getAssessment } from "../api/client";
import { AssessmentResult } from "../components/AssessmentResult";
import { PageHeader } from "../components/PageHeader";
import { ErrorState, LoadingBlock } from "../components/StateViews";
import { useModel } from "../context/ModelContext";
import type { AssessmentResponse } from "../types/api";

/** Reopens a stored prediction with its recommendations. */
export default function AssessmentDetailPage() {
  const { id } = useParams();
  const { features } = useModel();
  const [data, setData] = useState<AssessmentResponse | null>(null);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [tick, setTick] = useState(0);
  const num = Number(id);
  const valid = Number.isInteger(num) && num > 0;

  useEffect(() => {
    if (!valid) return;
    let off = false;
    setData(null); setError(null);
    getAssessment(num).then((d) => { if (!off) setData(d); }).catch((e) => { if (!off) setError(e); });
    return () => { off = true; };
  }, [num, valid, tick]);

  return (
    <>
      <PageHeader title={valid ? `Assessment #${num}` : "Assessment"} intro="A stored prediction and the recommendations for it." />
      {!valid && <ErrorState error={new Error("This is not a valid assessment number.")} title="Cannot open this record" />}
      {valid && !data && !error && <LoadingBlock label="Loading the assessment…" />}
      {error && <ErrorState error={error} onRetry={() => setTick((t) => t + 1)} title="Could not open this assessment" />}
      {data && <AssessmentResult a={{ ...data, saved: false, duplicate: false }} features={features} actions={<Button component={Link} to="/history" variant="default" className="no-print">Back to history</Button>} />}
    </>
  );
}

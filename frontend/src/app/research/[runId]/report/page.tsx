import { ReportView } from "@/components/report-view";

type ReportPageProps = {
  params: Promise<{
    runId: string;
  }>;
};

export default async function ReportPage({ params }: ReportPageProps) {
  const { runId } = await params;
  return <ReportView runId={runId} />;
}

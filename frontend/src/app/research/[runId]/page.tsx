import { ResearchRunDetail } from "@/components/research-run-detail";

type ResearchRunPageProps = {
  params: Promise<{
    runId: string;
  }>;
};

export default async function ResearchRunPage({ params }: ResearchRunPageProps) {
  const { runId } = await params;
  return <ResearchRunDetail runId={runId} />;
}

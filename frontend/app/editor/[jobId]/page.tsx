import { EditorWorkspace } from "@/components/editor/EditorWorkspace";

export default function EditorPage({ params }: { params: { jobId: string } }) {
  return <EditorWorkspace jobId={params.jobId} />;
}

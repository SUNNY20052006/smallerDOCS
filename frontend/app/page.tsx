import { UploadDropzone } from "@/components/upload/UploadDropzone";

export default function HomePage() {
  return (
    <main className="min-h-screen bg-card px-6 py-12">
      <section className="mx-auto max-w-5xl">
        <div className="mb-8">
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">smallerDOCS</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            Upload a scanned or digital legal document to reconstruct it into an editable document.
          </p>
        </div>
        <UploadDropzone />
      </section>
    </main>
  );
}

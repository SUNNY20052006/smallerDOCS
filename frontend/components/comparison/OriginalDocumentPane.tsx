"use client";

import { Minus, Plus } from "lucide-react";
import { useState } from "react";
import { Slider } from "@/components/ui/Slider";
import type { Block, DocumentModel } from "@/lib/types/idm";
import { getPageImageUrl } from "@/lib/api/document";
import { useComparisonStore } from "@/store/useComparisonStore";

const MIN_ZOOM = 25;
const MAX_ZOOM = 200;
const STEP = 5;

export function OriginalDocumentPane({ document }: { document: DocumentModel }) {
  const active = useComparisonStore((state) => state.activeSourceBlockId);
  const setActive = useComparisonStore((state) => state.setActiveSourceBlockId);
  const [zoom, setZoom] = useState(100);

  return (
    <div className="relative h-full min-h-0 bg-muted/50">
      <div className="absolute inset-0 overflow-auto">
        <div
          className="mx-auto flex max-w-full flex-col gap-6 p-4"
          style={{ transform: `scale(${zoom / 100})`, transformOrigin: "top center" }}
        >
          {document.pages.map((page) => (
            <div key={page.pageNumber} className="relative mx-auto overflow-hidden bg-card shadow" style={{ width: Math.min(page.width / 3, 760), aspectRatio: `${page.width}/${page.height}` }}>
              <img
                src={getPageImageUrl(document.documentId, page.pageNumber)}
                alt={`Original page ${page.pageNumber}`}
                className="absolute inset-0 h-full w-full object-fill"
                draggable={false}
              />
              {page.blocks.flatMap(flattenBlocks).map((block) =>
                block.bbox ? (
                  <button
                    key={block.id}
                    aria-label={`Source block ${block.id}`}
                    className={`absolute border transition ${active === block.id ? "border-primary bg-primary/10" : "border-transparent hover:border-ring hover:bg-accent/30"}`}
                    style={{
                      left: `${(block.bbox.x / page.width) * 100}%`,
                      top: `${(block.bbox.y / page.height) * 100}%`,
                      width: `${(block.bbox.width / page.width) * 100}%`,
                      height: `${(block.bbox.height / page.height) * 100}%`,
                    }}
                    onClick={() => setActive(block.id)}
                  />
                ) : null,
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="absolute bottom-8 right-6 z-10 flex items-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-1.5 shadow-sm">
        <button
          type="button"
          title="Zoom out"
          className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground hover:bg-accent disabled:opacity-30"
          disabled={zoom <= MIN_ZOOM}
          onClick={() => setZoom((z) => Math.max(MIN_ZOOM, z - STEP))}
        >
          <Minus className="h-3.5 w-3.5" />
        </button>
        <Slider
          value={[zoom]}
          onValueChange={([v]) => setZoom(v)}
          min={MIN_ZOOM}
          max={MAX_ZOOM}
          step={STEP}
          className="w-40"
        />
        <button
          type="button"
          title="Zoom in"
          className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground hover:bg-accent disabled:opacity-30"
          disabled={zoom >= MAX_ZOOM}
          onClick={() => setZoom((z) => Math.min(MAX_ZOOM, z + STEP))}
        >
          <Plus className="h-3.5 w-3.5" />
        </button>
        <span className="w-8 text-right text-[11px] tabular-nums text-muted-foreground">{zoom}%</span>
      </div>
    </div>
  );
}

function flattenBlocks(block: Block): Block[] {
  return [block, ...(block.children ?? []).flatMap(flattenBlocks)];
}

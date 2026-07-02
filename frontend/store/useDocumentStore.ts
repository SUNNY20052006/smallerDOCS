import { create } from "zustand";
import type { TiptapDocument } from "@/lib/types/api";
import type { DocumentModel } from "@/lib/types/idm";

interface DocumentState {
  document: DocumentModel | null;
  tiptapDoc: TiptapDocument | null;
  dirty: boolean;
  setDocument: (document: DocumentModel, tiptapDoc: TiptapDocument) => void;
  setTiptapDoc: (tiptapDoc: TiptapDocument) => void;
}

export const useDocumentStore = create<DocumentState>((set) => ({
  document: null,
  tiptapDoc: null,
  dirty: false,
  setDocument: (document, tiptapDoc) => set({ document, tiptapDoc, dirty: false }),
  setTiptapDoc: (tiptapDoc) => set({ tiptapDoc, dirty: true }),
}));

import { create } from "zustand";

interface ComparisonState {
  activeSourceBlockId: string | null;
  hoveredBlockId: string | null;
  setActiveSourceBlockId: (id: string | null) => void;
  setHoveredBlockId: (id: string | null) => void;
}

export const useComparisonStore = create<ComparisonState>((set) => ({
  activeSourceBlockId: null,
  hoveredBlockId: null,
  setActiveSourceBlockId: (activeSourceBlockId) => set({ activeSourceBlockId }),
  setHoveredBlockId: (hoveredBlockId) => set({ hoveredBlockId }),
}));

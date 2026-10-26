import { useQuery } from "@tanstack/react-query";

import { api } from "../../shared/api/client";
import type { DiffRow, DocumentVersion } from "../../shared/api/types";

export { useDocuments } from "../ask/api";

export const useDocumentVersion = (docKey: string, version: number) =>
  useQuery({
    queryKey: ["document", docKey, version],
    queryFn: () =>
      api.get<DocumentVersion>(`/api/documents/${encodeURIComponent(docKey)}/versions/${version}`),
  });

export const useDiff = (docKey: string, a: number, b: number, enabled: boolean) =>
  useQuery({
    queryKey: ["diff", docKey, a, b],
    queryFn: () => api.get<DiffRow[]>(`/api/documents/${encodeURIComponent(docKey)}/diff?a=${a}&b=${b}`),
    enabled,
  });

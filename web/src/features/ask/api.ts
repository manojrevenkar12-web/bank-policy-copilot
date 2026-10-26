import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../shared/api/client";
import type { AskResult, DocumentSummary, HistoryItem } from "../../shared/api/types";
import { layout } from "../../shared/theme/tokens";

export const useAsk = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { question: string; as_of: string }) => api.post<AskResult>("/api/ask", v),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["history"] }),
  });
};

export const useHistory = () =>
  useQuery({
    queryKey: ["history"],
    queryFn: () => api.get<HistoryItem[]>(`/api/history?limit=${layout.historyItems}`),
  });

export const useDocuments = () =>
  useQuery({ queryKey: ["documents"], queryFn: () => api.get<DocumentSummary[]>("/api/documents") });

export const useFeedback = (queryId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { helpful: boolean; comment: string }) => api.post(`/api/queries/${queryId}/feedback`, v),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["history"] }),
  });
};

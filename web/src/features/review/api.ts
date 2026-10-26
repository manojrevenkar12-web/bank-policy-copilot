import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../shared/api/client";
import type { ImpactItem, ReviewItem } from "../../shared/api/types";

export const useReviewQueue = () =>
  useQuery({ queryKey: ["review"], queryFn: () => api.get<ReviewItem[]>("/api/review") });

export const useImpact = () =>
  useQuery({ queryKey: ["impact"], queryFn: () => api.get<ImpactItem[]>("/api/impact") });

export const useResolve = (kind: "review" | "impact") => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { id: number; resolution: string }) =>
      api.post(`/api/${kind}/${v.id}/resolve`, { resolution: v.resolution }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: [kind] }),
  });
};

export const useAuditCheck = () =>
  useMutation({
    mutationFn: () =>
      api.get<{ ok: boolean; records: number; broken_at: number | null }>("/api/audit/verify"),
  });

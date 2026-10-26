import { useMutation, useQuery } from "@tanstack/react-query";

import { api } from "../../shared/api/client";
import type { User } from "../../shared/api/types";
import { session } from "../../shared/lib/session";

export const useDemoUsers = () =>
  useQuery({ queryKey: ["demo-users"], queryFn: () => api.get<User[]>("/api/demo-users"), retry: false });

export const useSignIn = () =>
  useMutation({
    mutationFn: (login: string) => api.post<{ token: string; user: User }>("/api/session", { login }),
    onSuccess: (s) => session.set(s),
  });

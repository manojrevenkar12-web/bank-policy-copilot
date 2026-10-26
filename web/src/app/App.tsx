import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "framer-motion";
import { lazy, Suspense, type ReactNode } from "react";
import { createBrowserRouter, Navigate, RouterProvider } from "react-router-dom";

import { LoginPage } from "../features/auth/LoginPage";
import { ApiError } from "../shared/api/client";
import { SkeletonBlock } from "../shared/ui";
import { Layout, RequireReviewer } from "./Layout";

const AskPage = lazy(() => import("../features/ask/AskPage").then((m) => ({ default: m.AskPage })));
const DocumentsPage = lazy(() =>
  import("../features/documents/DocumentsPage").then((m) => ({ default: m.DocumentsPage })),
);
const DocumentPage = lazy(() =>
  import("../features/documents/DocumentPage").then((m) => ({ default: m.DocumentPage })),
);
const ReviewPage = lazy(() =>
  import("../features/review/ReviewPage").then((m) => ({ default: m.ReviewPage })),
);
const EvaluationPage = lazy(() =>
  import("../features/evaluation/EvaluationPage").then((m) => ({ default: m.EvaluationPage })),
);

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (count, err) => !(err instanceof ApiError && err.status >= 400 && err.status < 500) && count < 2,
    },
  },
});

const page = (el: ReactNode) => (
  <Suspense fallback={<SkeletonBlock lines={6} label="Seite wird geladen" />}>{el}</Suspense>
);

const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    element: <Layout />,
    children: [
      { index: true, element: page(<AskPage />) },
      { path: "richtlinien", element: page(<DocumentsPage />) },
      { path: "richtlinien/:docKey/:version", element: page(<DocumentPage />) },
      { path: "pruefung", element: <RequireReviewer>{page(<ReviewPage />)}</RequireReviewer> },
      { path: "qualitaet", element: page(<EvaluationPage />) },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      {/* Animations follow the operating system's reduced-motion setting. */}
      <MotionConfig reducedMotion="user">
        <RouterProvider router={router} />
      </MotionConfig>
    </QueryClientProvider>
  );
}

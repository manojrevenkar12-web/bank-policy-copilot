import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { AnswerCard, NoAnswer } from "../src/features/ask/AnswerCard";
import { VersionBand } from "../src/features/ask/VersionBand";
import { EmptyState, QueryState, SkeletonBlock } from "../src/shared/ui";
import { answered } from "./fixtures";

const versions = [
  { version: 1, valid_from: "2022-03-01", valid_to: "2023-07-01" },
  { version: 2, valid_from: "2023-07-01", valid_to: "2025-04-01" },
  { version: 3, valid_from: "2025-04-01", valid_to: null },
];

describe("validity band", () => {
  it("draws every version and marks the cited one", () => {
    const { container } = render(
      <VersionBand versions={versions} asOf="2024-02-01" cited={2} today="2026-10-26" />,
    );
    expect(screen.getByText("V1")).toBeInTheDocument();
    expect(screen.getByText("V3")).toBeInTheDocument();
    expect(screen.getByTestId("as-of-marker")).toHaveTextContent("01.02.2024");
    expect(container.querySelector("figure")).toHaveAttribute(
      "aria-label",
      "Fassungen und Stichtag 01.02.2024",
    );
  });
});

describe("answers", () => {
  it("quotes the paragraph, names the source and says what applies today", () => {
    render(
      <MemoryRouter>
        <AnswerCard result={answered} doc={undefined} />
      </MemoryRouter>,
    );
    expect(screen.getByRole("blockquote")).toHaveTextContent("15.000 EUR");
    expect(screen.getByRole("link", { name: /Zahlungsverkehr/ })).toHaveAttribute(
      "href",
      "/richtlinien/RL-ZV-01/2#tz-2.1",
    );
    expect(screen.getByTestId("newer")).toHaveTextContent("10.000 EUR");
    expect(screen.getByText("am 01.02.2024 in Kraft")).toBeInTheDocument();
  });

  it("explains a missing answer without guessing", () => {
    render(
      <MemoryRouter>
        <NoAnswer result={{ ...answered, outcome: "no_answer", citations: [], newer: null }} />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "Keine Regelung gefunden" })).toBeInTheDocument();
    expect(screen.queryByText(/15\.000/)).not.toBeInTheDocument();
  });
});

function Harness({ fn }: { fn: () => Promise<string[]> }) {
  const q = useQuery({ queryKey: ["x", fn], queryFn: fn, retry: false });
  return (
    <QueryState
      query={q}
      skeleton={<SkeletonBlock lines={2} label="Lädt" />}
      isEmpty={(d) => d.length === 0}
      empty={<EmptyState title="Leer" />}
    >
      {(d) => <p>{d.join(",")}</p>}
    </QueryState>
  );
}
const wrap = (ui: React.ReactNode) =>
  render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>);

describe("loading, error and empty states", () => {
  it("shows a skeleton, then content", async () => {
    wrap(<Harness fn={async () => ["RL-ZV-01"]} />);
    expect(screen.getByRole("status", { name: "Lädt" })).toBeInTheDocument();
    expect(await screen.findByText("RL-ZV-01")).toBeInTheDocument();
  });
  it("shows the empty state", async () => {
    wrap(<Harness fn={async () => []} />);
    expect(await screen.findByRole("heading", { name: "Leer" })).toBeInTheDocument();
  });
  it("shows the error and retries", async () => {
    let n = 0;
    wrap(
      <Harness
        fn={async () => {
          n++;
          if (n === 1) throw new Error("Server weg");
          return ["zurück"];
        }}
      />,
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("Server weg");
    await userEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    expect(await screen.findByText("zurück")).toBeInTheDocument();
  });
});

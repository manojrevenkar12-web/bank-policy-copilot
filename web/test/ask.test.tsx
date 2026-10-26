import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { AskPage } from "../src/features/ask/AskPage";
import { session } from "../src/shared/lib/session";
import { answered } from "./fixtures";

function stubFetch(handler: (url: string, init?: RequestInit) => unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const body = handler(url, init);
      if (body instanceof Response) return body;
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }),
  );
}

const page = () =>
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <AskPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );

describe("asking", () => {
  beforeEach(() =>
    session.set({ token: "t", user: { login: "lena.vogt", name: "Lena Vogt", title: "", clearance: 2 } }),
  );
  afterEach(() => {
    vi.unstubAllGlobals();
    session.clear();
  });

  it("sends the question with the chosen date and shows the cited answer", async () => {
    const sent: unknown[] = [];
    stubFetch((url, init) => {
      if (url === "/api/ask") {
        sent.push(JSON.parse(String(init?.body)));
        return answered;
      }
      if (url.startsWith("/api/history")) return [];
      return [];
    });
    page();
    expect(await screen.findByRole("heading", { name: "Noch keine Fragen" })).toBeInTheDocument();
    await userEvent.type(
      screen.getByLabelText(/Was möchten Sie wissen/),
      "Ab welchem Betrag gilt das Vier-Augen-Prinzip?",
    );
    await userEvent.click(screen.getByRole("button", { name: "01.06.2024" }));
    await userEvent.click(screen.getByRole("button", { name: "Fragen" }));
    expect(await screen.findByTestId("answer")).toHaveTextContent("15.000 EUR");
    expect(sent).toEqual([
      { question: "Ab welchem Betrag gilt das Vier-Augen-Prinzip?", as_of: "2024-06-01" },
    ]);
  });

  it("shows the server's error and lets the user try again", async () => {
    let calls = 0;
    stubFetch((url) => {
      if (url === "/api/ask") {
        calls++;
        return calls === 1
          ? new Response(JSON.stringify({ detail: "Datenbank nicht erreichbar" }), { status: 503 })
          : { ...answered, outcome: "no_answer", citations: [], newer: null };
      }
      return [];
    });
    page();
    await userEvent.type(screen.getByLabelText(/Was möchten Sie wissen/), "Budget Weihnachtsfeier?");
    await userEvent.click(screen.getByRole("button", { name: "Fragen" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Datenbank nicht erreichbar");
    await userEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    expect(await screen.findByTestId("no-answer")).toBeInTheDocument();
  });
});

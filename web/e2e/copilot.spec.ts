import { expect, type Page, test } from "@playwright/test";

async function signIn(page: Page, login: string) {
  await page.goto("/login");
  await page.getByTestId(`login-${login}`).click();
  await expect(page).toHaveURL("/");
}

const nav = (page: Page, name: string) =>
  page.getByRole("navigation").getByRole("link", { name, exact: true }).click();

async function ask(page: Page, question: string, asOf?: string) {
  await page.getByLabel(/Was möchten Sie wissen/).fill(question);
  if (asOf) await page.locator("input[type=date]").fill(asOf);
  await page.getByRole("button", { name: "Fragen" }).click();
}

test("answers from the version in force on the date, and says what applies today", async ({ page }) => {
  await signIn(page, "lena.vogt");
  await ask(
    page,
    "Ab welchem Betrag müssen Zahlungen im Vier-Augen-Prinzip freigegeben werden?",
    "2024-02-01",
  );
  const answer = page.getByTestId("answer");
  await expect(answer).toContainText("15.000 EUR");
  await expect(answer).toContainText("Tz. 2.1 in Version 2");
  await expect(page.getByTestId("newer")).toContainText("10.000 EUR");
  await expect(page.getByTestId("as-of-marker")).toContainText("01.02.2024");
});

test("does not answer from a policy the user may not read", async ({ page }) => {
  await signIn(page, "paul.neumann");
  await ask(page, "Ab welchem Betrag müssen Zahlungen im Vier-Augen-Prinzip freigegeben werden?");
  await expect(page.getByTestId("no-answer")).toBeVisible();
  await expect(page.getByText("10.000 EUR")).toHaveCount(0);
  await nav(page, "Richtlinien");
  await expect(page.getByText("Reisekostenrichtlinie")).toBeVisible();
  await expect(page.getByText("Freigabe und Kontrolle im Zahlungsverkehr")).toHaveCount(0);
});

test("shows how the answer came about", async ({ page }) => {
  await signIn(page, "felix.brandt");
  await ask(page, "Wie hoch ist das VaR-Limit des Handelsbuchs?");
  await expect(page.getByTestId("answer")).toContainText("5.500.000 EUR");
  await page.getByRole("button", { name: /Wie die Antwort entstand/ }).click();
  await expect(page.getByTestId("answer").getByText("streng vertraulich")).toBeVisible();
  await expect(page.getByRole("cell", { name: /RL-TR-01 V2 Tz\./ }).first()).toBeVisible();
});

test("feedback reaches compliance, who can resolve it", async ({ page, browser }) => {
  await signIn(page, "aylin.demir");
  await ask(page, "Wie lange werden aufgezeichnete Beratungsgespräche aufbewahrt?");
  await expect(page.getByTestId("answer")).toBeVisible();
  await page.getByRole("button", { name: "Nein" }).click();
  await page.getByLabel("Was fehlt oder stimmt nicht?").fill("Bitte auch die Frist für E-Mails nennen");
  await page.getByRole("button", { name: "An Compliance senden" }).click();
  await expect(page.getByText("Compliance sieht sich die Antwort an")).toBeVisible();

  const reviewer = await (await browser.newContext()).newPage();
  await signIn(reviewer, "miriam.haas");
  await nav(reviewer, "Prüfung");
  const item = reviewer
    .getByTestId("review-item")
    .filter({ hasText: "Bitte auch die Frist für E-Mails nennen" });
  await expect(item).toBeVisible();
  await item.getByPlaceholder(/Vermerk/).fill("Frist für E-Mails ergänzt");
  await item.getByRole("button", { name: "Erledigt" }).click();
  await expect(item).toHaveCount(0);
});

test("a changed supervisory circular shows which policy still needs work", async ({ page }) => {
  await signIn(page, "miriam.haas");
  await nav(page, "Prüfung");
  const open = page.getByTestId("impact-item").filter({ hasText: "AM 1/2023" });
  await expect(open).toContainText("offen");
  await expect(open).toContainText("sechs Wochen");
  await expect(page.getByTestId("impact-item").filter({ hasText: "AM 2/2024" })).toContainText(
    "43 Tage später",
  );
});

test("compares two versions of a policy", async ({ page }) => {
  await signIn(page, "lena.vogt");
  await nav(page, "Richtlinien");
  await page.getByRole("link", { name: /Freigabe und Kontrolle im Zahlungsverkehr/ }).click();
  await page.getByText("Änderungen zu V2 zeigen").click();
  await expect(page.locator("del").filter({ hasText: "15.000 EUR" })).toBeVisible();
  await expect(page.locator("ins").filter({ hasText: "10.000 EUR" }).first()).toBeVisible();
});

test("a failing server shows an error with a retry, and the page recovers", async ({ page }) => {
  await signIn(page, "lena.vogt");
  let fail = true;
  await page.route("**/api/documents", async (route) => {
    if (fail) {
      await new Promise((r) => setTimeout(r, 400));
      return route.fulfill({ status: 500, body: JSON.stringify({ detail: "Wartung" }) });
    }
    return route.continue();
  });
  await page.goto("/richtlinien");
  await expect(page.getByRole("alert")).toContainText("Wartung", { timeout: 15_000 });
  await expect(page.getByRole("status", { name: /Richtlinien werden geladen/ })).toHaveCount(0);
  fail = false; // the server is back
  await page.getByRole("button", { name: "Erneut versuchen" }).click();
  await expect(page.getByText("Interne Richtlinien")).toBeVisible();
});

test("the quality page shows the blind test results", async ({ page }) => {
  await signIn(page, "lena.vogt");
  await nav(page, "Qualität");
  await expect(page.getByText("Blindtest v2, erster Lauf")).toBeVisible();
  await expect(page.getByRole("row", { name: /extractive/ })).toContainText("streng vertraulich");
});

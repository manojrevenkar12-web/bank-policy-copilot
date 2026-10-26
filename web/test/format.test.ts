import { formatDate, share, validity } from "../src/shared/lib/format";

describe("dates", () => {
  it("formats German dates and validity ranges", () => {
    expect(formatDate("2025-04-01")).toBe("01.04.2025");
    expect(validity("2023-07-01", "2025-04-01")).toBe("01.07.2023 bis 01.04.2025");
    expect(validity("2025-04-01", null)).toBe("seit 01.04.2025");
  });

  it("places a date on the band and clamps outside it", () => {
    expect(share("2024-01-01", "2023-01-01", "2025-01-01")).toBeCloseTo(0.5, 2);
    expect(share("2020-01-01", "2023-01-01", "2025-01-01")).toBe(0);
    expect(share("2030-01-01", "2023-01-01", "2025-01-01")).toBe(1);
    expect(share("2024-01-01", "2024-01-01", "2024-01-01")).toBe(0);
  });
});

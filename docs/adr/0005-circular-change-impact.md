# 5. When a supervisory circular changes, find the internal rules that implement it

## Decision

When a new version of a circular is ingested, each paragraph whose text changed is matched to
internal paragraphs that were in force on the circular's new date of effect: by explicit
reference ("vgl. AM 2/2024 Tz. 5") or by similar wording in a policy that cites the circular.
If the policy later got a version with a changed paragraph, the item is recorded as implemented
with the gap in days; otherwise it is open for Compliance to review.

## Consequences

In the simulated bank, AM 2/2024 shortened the reporting deadline for serious ICT incidents from
24 to 4 hours on 17.01.2025; the internal policy followed on 01.03.2025 (43 days later). AM 1/2023
lengthened the notice for material outsourcing from four to six weeks on 01.02.2026; the internal
policy still says four, so the item is open.

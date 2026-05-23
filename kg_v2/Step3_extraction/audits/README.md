# Step3 Audit and Verification Scripts

This directory contains one-off method audits, pilot reviews, verification
utilities, and artifact compaction tools used during Step3 Claim/Fact pipeline
development.

These scripts are retained for reproducibility and methodological traceability,
but they are not part of the main production pipeline. The active Step3 pipeline
entry points remain in `kg_v2/Step3_extraction/`.

Typical contents include:

- claim extraction policy audits;
- claim cap review and max-additional-claims verification utilities;
- supplementary extraction quality comparisons;
- full-run artifact compaction/audit helpers;
- fact builder selection policy audits;
- repair planning experiments.

Run these scripts only when intentionally reproducing a historical audit or
debugging a specific pipeline decision.

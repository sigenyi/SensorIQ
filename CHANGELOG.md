## [2.1.0] — Last updated 2026-05-28

Multi-phase release: UX overhaul (manual control, refinement chain, durable parsing), knowledge-base correction pass, new exposure-unit handling, and behavioral rewrites for more decisive, consistent recommendations.

### Added

- **Manual baseline button** — baseline no longer auto-fires on sidebar change. Yellow warning + “Regenerate Baseline” if setup changes mid-session.
- **Continuous refinement chain** — `refinement_history` in session state; each attempt appends rather than replaces. Prior attempts shown as collapsed expanders. Full chain passed to the AI so it does not repeat advice.
- Text area label adapts after the first attempt (“What still needs fixing?”).
- **Exposure-unit selector** — Seconds / Milliseconds / Fraction (1/n s) / Pulses. Normalized to seconds internally; AI recommends in the technician’s native unit.
- **Pulse knowledge** in KB (1 pulse = 1/60 s ≈ 0.0167 s); conversion references added to `quick_guide.txt` and `radiography_guide.txt`.
- **CareStack** added to software dropdown (TWAIN). Dropdown now alphabetically sorted.
- Default-to-TWAIN fallback rule for any software not in the FUSE list (incl. “OTHER”).

### Changed

- Refinement output strict-enforced into `Likely cause:` (1 sentence) → `Changes to make:` (bullets) → `Watch for:` (1-line risk or None). All internal reasoning now happens silently.
- **Delimiter-based log parsing** (`---LOGDATA--- / ---ENDLOG---`) replaces fragile line-by-line tag scanning. `LOG_ISSUE` and `LOG_SETTINGS` now write reliably regardless of model formatting variation.
- **Change Sizing rule** replaces the rigid 5–10% / max 20% jump cap from v1.0.0/v1.0.3 — adjustment size now scales to symptom severity, with clipping/saturation as the only hard limit.
- **Hardware & Binning Discipline** — exposure-time changes and 2x2 Binning are no longer default fallbacks when the AI is stuck; reserved for genuine under/over-exposure, saturation, weak sources, or sensor fatigue.
- **Unified output format** — both models share one behavioral spec (`SHARED_RULES`) and one fixed output skeleton (`HARDWARE/CAUSE → SETTINGS → NOTES`).
- S-Curve mechanic corrected: higher scale saves more tail data from both ends, producing more balanced shading.

### Fixed

- Gamma direction standardized to *lower = brighter* across the KB. Corrected inverted entries in `differential_diagnosis.txt` (A4/B3), `quick_guide.txt` Recipe D, and the `sensor_model.txt` interaction matrix.
- Removed impossible “Gamma > 1.0” recommendations from `radiography_guide.txt` (range is capped at 0.85).
- Sharpen Weight cap raised to 2.00 in `settings_guide.txt` to match the Caries recipe.
- CLAHE Num Regions range corrected to **2–8** (was 4–8); parameter now forced into every CLAHE recommendation (was being silently dropped).
- Integration list cleanup: deduped MiPACS; added 8 previously unclassified softwares (CLASSIC, Archy, Mogo, Acteon, VisionX, OneView, Umbie DentalCare, Harmony) to TWAIN.

### Removed

- `confirmed_structures` column and the structured-structure multiselect (both added in v2.0.0). Google Sheets schema reverted to the original 5-column format. Reason: client acceptance is inherently subjective and shouldn’t be constrained to a checklist.

-----

## [2.0.0] — Knowledge Expansion + App Rewrite

Three new mechanistic knowledge files plus an app rewrite to use them.

### Added — Knowledge Base

- **`sensor_model.txt`** — Jazz CMOS signal chain, 14-bit ADC (16,384 gray levels), linear response to ~88% of dynamic range, kVp/mAs effects on the raw pixel histogram, **parameter interaction risk matrix** flagging dangerous combinations.
- **`differential_diagnosis.txt`** — symptom-to-cause inverse reasoning tree across 7 categories (A–G) with disambiguation questions, plus a 5-tier escalation ladder (hardware → AN → CLAHE → Gamma → Sharpening → Contrast/Brightness as last resort).
- **`success_criteria.txt`** — five diagnostic structures (Lamina Dura, PDL, Trabecular Bone, Alveolar Crest, Caries) with objective visibility criteria, a diagnostic-goal → criteria matrix, and a minimum acceptable image standard.

### Added — Application

- `check_saturation_risk()` runs before any AI call; flags kVp/mAs above sensor saturation thresholds (Wall-mount: kVp ≥ 80 or mAs > 1.0; Hand-held: kVp ≥ 75 or mAs > 3.0). Shown in sidebar.
- **Diagnostic Goal sidebar selector** (6 options) passed into both prompts so the AI references the right recipe and success criteria.
- **Five-step reasoning protocol** embedded in both prompts: sensor check → history → recipe → interaction matrix → success criteria.
- Knowledge loader extended to load all six `.txt` files in protocol order.
- Tightened output formats for both baseline and troubleshooting prompts.

-----

## [1.0.3]

- **Soft constraint** on Contrast/Brightness — Gamma, CLAHE, and AN prioritized; Contrast/Brightness allowed only as last resort.
- **Inversion logic** added to both models: radiopaque (enamel/metal) = white, radiolucent (air/decay) = black.
- Refinement output forced into compact Summary + Actions (Old → New) format.
- Sidebar inputs for kVp, mA, and exposure time passed into the prompt.
- Knowledge loader extended to include `radiography_guide.txt`.
- `max_tokens` raised: Sonnet 600, Haiku 800.
- Removed Notion “Feedback” button.
- Refactored main `if/else` block; resolved `IndentationError`s around Analyze and Logging.

-----

## [1.0.0] — Foundation

- **Dual-model architecture**: Sonnet for baseline synthesis, Haiku for real-time refinement.
- `get_ai_baseline()` pulls all successful logs for the software/machine combo and synthesizes a Smart Baseline via Sonnet.
- `load_technical_manuals()` injects `quick_guide.txt` and `settings_guide.txt` into every prompt.
- Adaptive Normalization logic clarified in prompt: percentile number directly equals % of data removed.
- **STEADY STATE rule**: ~5–10% incremental adjustments. *(Superseded by Change Sizing in v2.1.0.)*

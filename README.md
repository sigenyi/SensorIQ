# SensorIQ — AI Image Quality Assistant

A Streamlit web application that helps dental imaging technicians configure the post-capture software settings of the Jazz CMOS X-ray sensor so the final radiograph is diagnostically usable for the dentist and acceptable to the client.

The app does **not** control X-ray hardware and does **not** analyze radiographs — it works on the software processing layer that runs after image capture, and it informs the technician’s judgment rather than replacing it.

-----

## Status

**Final release: v2.2.0.** Active development on this project has ended. The codebase, knowledge base, and prompt architecture are stable and intended for production use as-is. No further changes are planned.

-----

## ⚠ Critical: customize `sensor_model.txt` for your equipment

The knowledge file `knowledge/sensor_model.txt` is built around the **Jazz CMOS sensor** (functionally equivalent to the DEXIS Platinum). It documents the specific physical behavior the AI uses to reason mechanistically — bit depth, dynamic range, saturation threshold, scintillator type, the parameter-interaction risk matrix.

**If you are using a different sensor, update `sensor_model.txt` to match your hardware before deploying.** Otherwise the AI’s mechanistic reasoning will be wrong for your equipment and its recommendations will be unreliable on novel cases — which defeats the main purpose of the tool.

The values that are equipment-dependent and should be verified or replaced:

- **ADC bit depth** (currently 14-bit / 16,384 gray levels) — check your sensor’s published spec.
- **Linear-response range** (currently linear to ~88% of dynamic range) — check your sensor’s response curve.
- **Saturation threshold** (currently ~14,400 ADU) — derives from your sensor’s ADC and dynamic range.
- **Resolution** (currently 20+ lp/mm) — check your sensor’s spec sheet.
- **Scintillator type** (currently CsI:Tl with columnar microstructure) — some sensors use Gd₂O₂S or alternate CsI configurations, which changes light-spread and OFD-blur behavior.
- **The saturation thresholds in `check_saturation_risk()` in `streamlit_app.py`** (currently Wall-mount: kVp ≥ 80 or mAs > 1.0; Hand-held: kVp ≥ 75 or mAs > 3.0) are calibrated for the Jazz sensor; re-validate against your sensor’s actual saturation point.

If your sensor’s specs are not published, calibrate empirically against test exposures at known kVp/mAs and write the measured values into `sensor_model.txt`. The other five knowledge files are largely sensor-agnostic and do not need changes, though the recommended exposure-time ranges in `quick_guide.txt` may need adjustment if your sensor’s sensitivity differs substantially.

-----

## What it does

When a Jazz sensor is installed at a new dental office, getting the image to look right for that specific imaging software, X-ray machine, and dentist preference can take significant trial and error. The app captures that knowledge from senior technicians, standardizes it, and makes it available to any tech through an AI interface.

The technician workflow:

1. **Setup** — Select the imaging software, X-ray source (wall-mount or hand-held), and diagnostic goal. Enter hardware settings (kVp, mA, exposure time in the unit the machine uses — seconds, milliseconds, fraction `1/n s`, or pulses).
1. **Generate Baseline** — Click the button to have the AI synthesize a recommended starting configuration from physics knowledge, past successful calibrations for this software/machine pair, and the diagnostic recipe.
1. **Refine** — If the client is not happy, describe the problem in plain language (“bone looks washed out,” “image is too grainy”). The AI returns a short, direct response: likely cause, parameter changes, one-line risk note.
1. **Chain refinements** — Each new feedback round preserves history. The AI sees what has already been tried, does not repeat advice, and at attempt #3+ is required to propose a fundamentally different approach if prior rounds have not resolved the issue.
1. **Log** — When the client is happy, log the session. The software, machine, issue tag, final settings, and tech notes are appended to Google Sheets and feed future baselines for the same setup.

-----

## Tech stack

- **Frontend:** Streamlit (Python), deployable on Streamlit Cloud.
- **AI models:** Anthropic Claude — `claude-sonnet-4-6` for baseline synthesis, `claude-opus-4-7` for refinement. Refinement uses the more capable model because it’s where mid-session reasoning under pressure matters most.
- **Database:** Google Sheets via `streamlit-gsheets` (lightweight calibration log).
- **Knowledge base:** Six `.txt` files in `/knowledge/` loaded by `load_technical_manuals()` and injected into every AI prompt.

-----

## Knowledge files

- **`sensor_model.txt`** — Physical sensor behavior. **Equipment-specific — see warning above.**
- **`settings_guide.txt`** — Every Jazz software parameter (range, default, direction, use), the FUSE vs. TWAIN integration list, and global behavioral rules (Change Sizing, Anti-Loop, Hardware & Binning Discipline, Contrast & Brightness framing).
- **`quick_guide.txt`** — Recommended exposure times by region and machine type, diagnostic recipes (caries, perio, endo, fracture), and exposure-unit conversions including pulse equivalents.
- **`radiography_guide.txt`** — X-ray physics, image processing pipeline order, anatomical landmarks, AI decision matrix.
- **`differential_diagnosis.txt`** — Symptom → root cause → fix inverse reasoning tree across seven symptom categories (A–G), with a five-tier escalation ladder.
- **`success_criteria.txt`** — Five diagnostic structures (lamina dura, PDL space, trabecular bone, alveolar crest, caries) with objective visibility criteria and a goal → criteria matrix.

-----

## Setup

```bash
git clone https://github.com/sigenyi/SensorIQ.git
cd SensorIQ
pip install -r requirements.txt
```

### Secrets

Create `.streamlit/secrets.toml`:

```toml
CLAUDE_KEY = "your-anthropic-api-key"

[connections.gsheets]
spreadsheet = "your-google-sheet-url"
type = "service_account"
# ...your service account credentials
```

**API key requirements:** the key must have access to both `claude-sonnet-4-6` (baseline) and `claude-opus-4-7` (refinement). Most paid Anthropic tiers include both; verify Opus access before deploying. If you need Sonnet-only, change `REFINEMENT_MODEL` in `streamlit_app.py` to `"claude-sonnet-4-6"`.

### Run

```bash
streamlit run streamlit_app.py
```

-----

## Google Sheets schema

Five columns: `machine`, `software`, `issue`, `settings`, `notes`. The AI reads the last 10 rows for the current software+machine pair when generating a baseline. The practical sweet spot is 5–10 logs per pair — enough to show patterns, not so many that the prompt window gets noisy.

-----

## What this app is NOT

- Not a diagnostic tool — it does not analyze the radiograph image itself.
- Not hardware control — it does not control any X-ray machine or sensor.
- Not a replacement for technician judgment — all final decisions about image acceptability belong to the technician and the dentist.

-----

## Acknowledgements

The sensor mechanistic model draws on published CMOS sensor research, including the phantom-based clinical study by İncebeyaz et al. (*Comparison of Dental Intraoral Digital Imaging Systems Using Simulation Phantoms*, BJSTR 2023), and on DEXIS Platinum sensor specifications as the closest published architectural equivalent to the Jazz sensor.

See `CHANGELOG.md` for the full version history.

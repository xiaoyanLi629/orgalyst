# Orgalyst: a conversational analysis system for organoid bright-field images

**Category: End-to-End System**

Demo video (≤ 5 min, public): `<video link, to be added>`
Code repository (public, reproducible): https://github.com/xiaoyanLi629/orgalyst
Technical report: `docs/technical_report_en.html` (English, 19 pages) and `docs/technical_report.html` (Chinese, 18 pages) in the repository
Model weights: https://huggingface.co/XiaoyanLi/orgalyst-weights
Data: OrgLine (Zenodo 16355179, CC-BY-4.0); no private data was used

## In one sentence

A bench scientist tells the assistant "analyse these intestinal organoid images, compare the area of the two groups and give me a report", and a few minutes later receives an analysis report that can go into the lab record and still be verified three months later; every number in it can be recomputed from the command line without any large language model.

## The problem

Organoid and organ-on-a-chip experiments produce large numbers of bright-field micrographs every day, and the three questions asked most often are how many, how big, and has anything changed. Existing tools are either scripts that need an environment and a tuned diameter parameter, or software that segments but leaves measurement, statistics and record-keeping to the user. Turning a folder of images into a report still takes half a day, and three months later nobody can say which model and which parameters produced a given area.

## What we built

Two layers.

**The `orgalyst` toolkit (deterministic, no LLM)**
- Cellpose segmentation with organ-specific weights (cyto3 fine-tuned on OrgLine separately for brain, intestine, pancreatic cancer and colon) and a per-organ diameter strategy (model diameter / per-image size estimate / two-pass inference), which fixes the scale failure that is Cellpose's most common problem on organoids.
- A three-organ YOLO11m detector that only answers "how many", with counting thresholds calibrated on the validation set instead of the default.
- Morphometry (area, equivalent diameter, perimeter, circularity, solidity, aspect ratio, border flag; micrometres when a pixel size is given), two-level quality control (image-level sharpness / illumination / saturation; instance-level flip-rotate agreement that flags unreliable segmentations), group statistics (Mann-Whitney / Kruskal, Cliff's delta, Holm) and growth curves.
- A single-file HTML report and a run manifest recording input md5, weight hashes, parameters and software versions, so anyone can reproduce a run.

**The conversational assistant (Claude Agent SDK + MCP)**
- The toolkit is exposed as six MCP tools; the assistant interprets the request, picks the organ weights, passes parameters, checks and explains results. It never looks at pixels or computes numbers itself.
- The analysis protocol is written as a skill: confirm organ, pixel size and goal; choose tools; check the returned values (outlying counts trigger a look at the overlay; border exclusions and low-confidence counts must appear in the answer); report in a fixed format. Without a pixel size it never gives micrometre figures.
- Terminal and web editions (multi-account, permission gatekeeper, spending limits); an open-model gateway can be substituted for the API.

## Results (OrgLine test sets)

| Experiment | Result |
|---|---|
| E1 segmentation AP50 (zero-shot cyto3 → per-organ fine-tuning + diameter strategy) | brain 0.005 → 0.967; intestine 0.544 → 0.812; colon 0.405 → 0.815; pdac 0.419 → 0.591 |
| E1 cross-organ | leave-one-organ-out models reach only 0.15–0.47 on unseen organs, so organ-specific weights are necessary; fine-tuned Cellpose-SAM matches but does not beat fine-tuned cyto3 with 50× larger weights, not adopted |
| E2 counting by detection (joint YOLO11m) | mAP50 intestine 0.948 / brain 0.995 / lung 0.936; after threshold calibration the counting error falls from 0.262 to 0.207 (intestine) and 0.235 to 0.168 (lung) |
| E3 agreement with expert annotation (brain, 240 images) | Spearman 0.963, median relative error 1.9%, 93% of images within 10% |
| E4 quality control | the share of wrong instances among those flagged "low confidence" is 3.5–6.8× that of the rest (used as a hint, not a filter) |
| E5 end-to-end agent benchmark (12 natural-language tasks, judged automatically) | 12/12 passed, 113 s and 10.5 tool calls per task on average, 5.6 USD in total |

## Limitations, stated plainly

Recall on pancreatic cancer organoids is only about one half (test images have seven times the instance density of training images and come from a different instrument); only the brain dataset has a pixel calibration, so other organs are reported in pixels; the agent path was evaluated on one backend (Claude) and depends on a paid API. The command-line path has no such dependency and reproduces every number in the report.

## Reproduction

`pip install -r requirements.txt` → `bash scripts/download_weights.sh` → `python -m orgalyst analyze --organ intestine --images DIR --out runs`. The script order and expected wall time for reproducing every table are in the README and section 10 of the technical report; the repository already contains all result files we produced. A Dockerfile covers the command-line path.

## Team

Xiaoyan Li (AI / computer vision / LLM applications, project lead); `<biologist colleague>` (organoid culture and morphological interpretation, responsible for requirements and review of results). Claude Code was used as a coding assistant during development; all code, documents and experiment scripts were reviewed by the authors.

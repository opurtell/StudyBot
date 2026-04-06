# Project Audit: Unfinished Work and Disconnected Artefacts

Date: 2026-04-05

Scope: full repository review for unfinished work, disconnected UI/backend paths, placeholder logic, and ideas tracked as complete but not fully implemented.

Note: `TODO.md` was updated after this audit to align with the codebase. The tracker-related notes below reflect that updated state.

## Executive Summary

The project is broadly functional, but there are several places where the implementation stops short of what the UI copy, TODO tracker, or backend surface implies.

The highest-signal findings are:

1. The Library page renders a `New Documentation` button with no action.
2. The Guidelines page exposes a three-option revision scope picker, but Quiz startup ignores that state entirely.
3. Guideline detail responses include `dose_lookup` and `flowchart`, but the frontend never renders either field.
4. The backend supports CMG refresh endpoints, but the Settings UI only wires `Re-run Pipeline` and `Clear Vector Store`.
5. The feedback action labelled `Request Peer Review` is only a route change back to `/quiz`.
6. The flowchart pipeline is still mock logic despite TODO claiming SVG flowchart extraction is complete.
7. The repo still contains root-level exploratory scripts and output files that are not part of the app or test entrypoints.

## Confirmed Code-Level Findings

### 1. Dead button on Library page

Status: Confirmed disconnected UI

Evidence:
- [`src/renderer/pages/Library.tsx`](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/renderer/pages/Library.tsx#L33) renders `New Documentation`.
- The button has no `onClick`, no link, and no surrounding handler.

Impact:
- Visible control with no behaviour.
- Now correctly tracked in `TODO.md` as partial.

### 2. Guideline revision scope picker is not connected to quiz behaviour

Status: Confirmed disconnected feature

Evidence:
- [`src/renderer/pages/Guidelines.tsx`](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/renderer/pages/Guidelines.tsx#L100) sends `scope`, `guidelineId`, and `section` via router state.
- [`src/renderer/hooks/useQuizSession.ts`](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/renderer/hooks/useQuizSession.ts#L86) starts sessions only from the explicit `StartSessionRequest` passed by UI controls.
- No code in Quiz startup reads router state from Guidelines.

Impact:
- `This Guideline`, `This Section`, and `All Guidelines` currently behave the same from the user’s perspective.
- The scope picker is presentation without downstream logic.

### 3. Guideline detail carries extra data that the UI drops

Status: Confirmed dead data path

Evidence:
- [`src/python/guidelines/router.py`](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/python/guidelines/router.py#L131) includes both `dose_lookup` and `flowchart` in guideline detail responses.
- [`src/renderer/pages/Guidelines.tsx`](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/renderer/pages/Guidelines.tsx#L299) renders only `detail.content_markdown`.

Impact:
- Backend work exists that is not visible to users.
- The app does not surface dose tables or flowchart content inside the guideline browser despite the data contract supporting it.

### 4. CMG refresh backend exists but is not wired into Settings UI

Status: Confirmed backend/frontend disconnect

Evidence:
- [`src/python/settings/router.py`](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/python/settings/router.py#L148) exposes `GET /settings/cmg-refresh`.
- [`src/python/settings/router.py`](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/python/settings/router.py#L153) exposes `POST /settings/cmg-refresh/run`.
- [`tests/python/test_settings_router.py`](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/tests/python/test_settings_router.py#L13) covers those endpoints.
- [`src/renderer/providers/SettingsProvider.tsx`](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/renderer/providers/SettingsProvider.tsx#L14) only exposes `save`, `saveModels`, `rerunPipeline`, `clearVectorStore`, and `refetch`.
- [`src/renderer/pages/Settings.tsx`](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/renderer/pages/Settings.tsx#L398) only renders `Re-run Pipeline` and `Clear Vector Store`.

Impact:
- A supported backend capability is not reachable in the app.
- Now correctly tracked in `TODO.md` as partial.

### 5. `Request Peer Review` is label-only behaviour

Status: Confirmed placeholder-like action

Evidence:
- [`src/renderer/pages/Feedback.tsx`](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/renderer/pages/Feedback.tsx#L86) labels the button `Request Peer Review`.
- The button action is only `navigate("/quiz")`.

Impact:
- No peer review request is created, queued, recorded, or otherwise handled.
- The label overstates the implemented behaviour.

### 6. Flowchart extraction is still mock logic

Status: Confirmed unfinished pipeline

Evidence:
- [`src/python/pipeline/cmg/flowcharts.py`](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/python/pipeline/cmg/flowcharts.py#L13) describes `convert_to_mermaid` as mock conversion.
- [`src/python/pipeline/cmg/flowcharts.py`](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/python/pipeline/cmg/flowcharts.py#L30) simulates a hardcoded `CMG_12`.
- [`src/python/pipeline/cmg/flowcharts.py`](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/python/pipeline/cmg/flowcharts.py#L38) uses `svg_mock`.

Impact:
- The flowchart stage is not extracting real flowcharts from CMG assets.
- Now correctly tracked in `TODO.md` as partial.

### 7. Root-level exploratory artefacts are not connected to the application

Status: Confirmed orphan artefacts

Files:
- `/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/capture_assets.py`
- `/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/test_ast.py`
- `/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/test_crawl.py`
- `/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/test_dom.py`
- `/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/test_modals.py`
- `/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/test_navigation.py`
- `/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/modals_output.txt`

Evidence:
- They are outside `tests/` and outside packaged runtime paths.
- Repository search did not find them wired into package scripts or the app runtime.
- The live CMG capture path is the separate in-tree module [`src/python/pipeline/cmg/capture_assets.py`](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/src/python/pipeline/cmg/capture_assets.py).

Impact:
- Repository noise.
- Harder to distinguish production pipeline code from one-off investigation artefacts.

## TODO Alignment

`TODO.md` now reflects the main gaps found in this audit more accurately. In particular, it now:

- tracks `New Documentation` as partial rather than complete
- tracks `Request Peer Review` as partial rather than complete
- tracks Settings data management as partial because CMG refresh is backend-only
- tracks the guideline scope picker as partial because the selected scope is not consumed
- tracks guideline `dose_lookup` and `flowchart` rendering as open work
- tracks the flowchart pipeline as partial because `flowcharts.py` is still mock logic
- marks `[REVIEW_REQUIRED]` review work complete
- removes the stale claim that the Library page still uses hardcoded source data

Residual note:
- The audit document is still useful because it explains the code evidence behind those TODO items, not just their existence.

## Explicitly Open Work Still Tracked as Unfinished

These do appear to remain legitimately open:

- [`TODO.md`](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/TODO.md#L68): extend the clinical dictionary as new terms are encountered.
- [`TODO.md`](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/TODO.md#L237): `Request Peer Review` remains partial and is still only a navigation action.
- [`TODO.md`](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/TODO.md#L245): `New Documentation` button remains visible but unwired.
- [`TODO.md`](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/TODO.md#L256): Settings data management still does not expose CMG refresh in the renderer.
- [`TODO.md`](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/TODO.md#L263): guideline scope picker UI exists but is not connected to quiz generation.
- [`TODO.md`](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/TODO.md#L264): guideline detail panel still does not render `dose_lookup` or `flowchart`.
- [`TODO.md`](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/TODO.md#L117): extract weight-band dose tables from the Critical Care Reference Cards chunk.
- [`TODO.md`](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/TODO.md#L121): use vision LLM for image-based flowcharts.
- [`TODO.md`](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/TODO.md#L122): validate reconstructed flowcharts against originals.
- [`TODO.md`](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/TODO.md#L120): SVG flowchart extraction is still only partial because the current module is stubbed.
- [`TODO.md`](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/TODO.md#L135): periodic CMG re-scraping plan.
- [`TODO.md`](/Users/oscarpurtell/claudeCode/studyBot/studyBotcode/TODO.md#L286): full pipeline integration testing remains minimal.

## Recommended Cleanup Order

1. Wire or remove the dead Library `New Documentation` button.
2. Either connect Guidelines scope selection into quiz session creation or remove the picker until implemented.
3. Expose CMG refresh in Settings to match the backend.
4. Rename or implement `Request Peer Review`.
5. Decide whether guideline detail should render `dose_lookup` and `flowchart`; if not, simplify the contract.
6. Reclassify `src/python/pipeline/cmg/flowcharts.py` as unfinished and either implement or clearly mark it as stub work.
7. Remove or relocate root-level exploratory scripts and artefact files.
8. Reconcile `TODO.md` so it reflects the actual state of the codebase.

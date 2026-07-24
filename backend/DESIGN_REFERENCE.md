# Design Reference — Ward Patient Management UI

This is the **target interface** the dashboard/backend should build toward.
Based on a reference screenshot of a hospital ward EHR (Comarch Healthcare-style).

## Overall layout

Three-column application shell:

```
┌────────────────────────────────────────────────────────────────────┐
│ TOP NAV (dark blue): Intensive Ward ▾ | Ward | Calendar | Patients | │
│   Treatment rooms ▾ | Tasks | Aggregate | Reports | Settlements ▾ |  │
│   Accounts ▾ | More ▾            [chat] [user: esapproject1 ▾] [pwr] │
├───────────────┬────────────────────────────────────────────────────┤
│ LEFT PANEL    │  PATIENT HEADER (teal)                              │
│               │  Name (ID, age) · Main Ledger No · Ward Ledger No   │
│ Search [⟳][▼] │  Doctor · Diagnosis · Room · Bed · eWUŚ · Visit     │
│ [1][2][3][4][5]│ ────────────────────────────────────────────────── │
│               │  TABS: Documents | Summary | Last events | Results  │
│ Patients at   │        | Requests | Medicine cards | Tasks |        │
│ the ward (14) │        Prescriptions and referrals                  │
│  • NAME  ⚠    │ ────────────────────────────────────────────────── │
│  • NAME       │  [doc category ▾]     RECORDS TABLE                 │
│  • NAME  ⚠    │  Search document [x]  Date | Person | Document | ▸  │
│  ...          │  Entry into main rec  2021-03-23  HEALTHCARE  ...   │
│               │  Careful hospitaliz.  2020-10-06  COMARCH     ...   │
│ [Add patient] │  ...                                                │
└───────────────┴────────────────────────────────────────────────────┘
```

## Components

### Top navigation
- Dark navy bar, white text, dropdown carets on several items.
- Items: Intensive Ward ▾, Ward, Calendar, Patients, Treatment rooms ▾,
  Tasks, Aggregate, Reports, Settlements ▾, Accounts ▾, More ▾.
- Right side: chat/message icon, current user (`esapproject1 ▾`), power/logout.

### Left panel — ward patient list
- Search input with refresh (⟳) and filter (▼) buttons.
- Row of quick-filter number tabs: 1 2 3 4 5.
- Header "Patients at the ward (14)" with a settings/gear affordance.
- Scrollable list of patients (surname first, e.g. HARRISON JOHN).
- Red warning triangle (⚠) badge on patients needing attention; some rows
  show a secondary status line in orange.
- Selected patient row highlighted (light blue).
- Full-width teal "Add patient" button pinned at the bottom.

### Patient header (teal band)
- Line 1: `SURNAME NAME  ⓘ  (Patient ID: 14, age: -)  Main Ledger No. /2/2021  Ward Ledger No. /2/2021`
- Line 2 (white sub-band): Doctor · Diagnosis · Room · Bed · eWUŚ (status,
  red "No data" when missing, with refresh) · Commercial visit (e.g. Unpaid).
- "Summary" action button on the right.

### Tab strip
Documents · Summary · Last events · Results · Requests · Medicine cards ·
Tasks · Prescriptions and referrals. (Active tab = teal underline/fill.)

### Documents tab body — two panes
1. **Left sub-pane (document picker)**
   - "Search document" input with clear (x).
   - Category dropdown (e.g. "Patient Admission").
   - List of document templates: Entry into main record, Careful
     hospitalization, Admission confirmation, End of pass, Completion of
     medical history, Epidemiological interview, Treatment plan, Condition
     upon admission, Change of bed, ...
2. **Right sub-pane (records table)**
   - Columns: **Date** | **Person** (with filter ▼) | **Document** (filter ▼)
     | **Action**.
   - Rows are timestamped record entries (e.g. `2021-03-23 15:57`,
     `HEALTHCARE COMARCH`, `Entry into ward record`).
   - Action column: folder / print / attachment icons per row.

## Palette
- Primary top nav: dark navy (`#1f3a5f`-ish, diagonal texture).
- Accent / active / primary button: teal (`#1aa7a0`-ish).
- Warnings: red triangle badges; orange secondary text.
- Body: white cards on light grey background.

## Notes / open questions for the user
- Confirm which framework renders this — extend the existing Django
  templates (`backend/templates/clinic/`) or a separate SPA front end?
- Confirm scope: is the full multi-tab patient chart in play, or start with
  the ward list + patient header + Documents tab?
- Confirm terminology/localisation (some labels read as translated from
  Polish, e.g. eWUŚ, "End of pass").

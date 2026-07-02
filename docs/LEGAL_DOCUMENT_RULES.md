# LEGAL_DOCUMENT_RULES.md

## Scope

These are reconstruction rules, not legal rules. Nothing here interprets, validates, or judges the
legal content or enforceability of a document. Every rule below governs one thing only: how
faithfully smallerDOCS turns a scanned or digital legal document into an editable one. This
document is the single source of truth for that fidelity — `OCR_PIPELINE.md`'s "Legal Rules
Engine" stage (Stage 10) is this document's implementation, and `EDITOR_SPECIFICATION.md` /
`EXPORT_SYSTEM.md` both defer to the rules here wherever formatting fidelity is in question.

Each rule states Purpose, Reasoning, an example input/output pair, and which pipeline stage
(`OCR_PIPELINE.md`) or layer (`EDITOR_SPECIFICATION.md`, `EXPORT_SYSTEM.md`) is responsible for
enforcing it.

---

### Rule 1 — Heading Preservation

| | |
|---|---|
| Purpose | Every heading in the source is reproduced as a `heading` block at the correct level, never demoted to plain text. |
| Reasoning | Legal documents use heading hierarchy (document title → article headings → section headings) to convey structural authority; flattening it to bold paragraphs loses that signal for anyone navigating or exporting the document. |
| Related pipeline stage | Block Classification (Stage 7), font-size-rank heuristic. |

**Example input**: A contract's document title "RESIDENTIAL LEASE AGREEMENT" set in 16pt bold,
followed by "1. TERM" in 13pt bold, followed by 11pt body text.

**Correct output**: Title → `heading` level 1. "1. TERM" → `clauseNumber` block (Rule 3) attached
to a `paragraph`, not itself a `heading` — clause labels are numbering, not document structure,
even when bolded (see Rule 3 for why these are kept distinct).

**Incorrect output**: Treating "1. TERM" as `heading` level 2 merely because it's bold — this
conflates two different structural systems (heading hierarchy vs. clause numbering) that the
Editor and Export layers handle differently.

**Implementation notes**: Heading-level assignment uses font-size *ranking* relative to the
page's modal body size, not absolute point size — a scan's OCR-estimated font size is not
reliable in absolute terms, only in relative comparison within the same document.

---

### Rule 2 — Paragraph Spacing and Indentation

| | |
|---|---|
| Purpose | Preserve each paragraph's vertical spacing from its neighbors and its horizontal indentation level. |
| Reasoning | Indentation in legal documents frequently signals nesting (a sub-clause indented under its parent clause) — collapsing it to a flat left margin destroys that signal even if the clause numbering itself survives. |
| Related pipeline stage | Formatting Reconstruction (Stage 9), `attrs.indentLevel` via left-bbox-offset banding. |

**Example input**: A clause at left margin, with a sub-paragraph indented 0.5" beneath it.

**Correct output**: Two `paragraph` blocks, the second with `attrs.indentLevel: 1` (one band
deeper than the first's `indentLevel: 0`).

**Incorrect output**: Both paragraphs emitted at `indentLevel: 0` because both were captured
inside the same layout region.

**Implementation notes**: Indent bands are computed per-document (not a fixed pixel threshold),
since scan DPI and original page-margin conventions vary; the modal left-bbox offset for
`indentLevel: 0` is established from the most common paragraph left-edge on the page.

---

### Rule 3 — Clause Hierarchy and Numbering

| | |
|---|---|
| Purpose | Reproduce clause/section numbers exactly as they appear, in whatever numbering system the source uses, and preserve their nesting depth. |
| Reasoning | Clause numbers in legal documents are load-bearing — clause "4.2(b)" is referenced elsewhere in the same document and possibly in related documents. Silently renumbering or restyling it breaks those references. |
| Related pipeline stage | Legal Rules Engine (Stage 10), `clause_numbering.py`. |

**Supported numbering styles** (pattern-matched, not guessed): `legal_decimal` (`1.`, `1.1`,
`1.1.1`), `roman` (`I.`, `II.`, `i.`, `ii.`), `alpha` (`A.`, `B.`, `(a)`, `(b)`), and combinations
of these across nesting depths (e.g. a `legal_decimal` top level containing `alpha` sub-items,
which is common in leases and contracts).

**Example input**: `"4. INDEMNIFICATION"` followed by `"(a) Tenant shall..."` followed by
`"(b) Landlord shall..."`.

**Correct output**: `clauseNumber` block with `numberingStyle: "legal_decimal", depth: 1, display:
"4."` attached to the first paragraph; two `clauseNumber` blocks with `numberingStyle: "alpha",
depth: 2, display: "(a)"` / `"(b)"` attached to the following two paragraphs.

**Incorrect output**: Converting `(a)`/`(b)` into a Word auto-numbered list — auto-numbering
renumbers automatically if items are added/removed, silently changing labels the original document
never intended to be dynamic. smallerDOCS numbering is always literal text, never a live counter
(see `EXPORT_SYSTEM.md`'s DOCX mapping, which deliberately writes clause numbers as literal bold
text runs, not Word list-numbering fields, for exactly this reason).

**Implementation notes**: Depth is tracked contiguously per-document (a running stack keyed by
numbering style), so `Rule 3`'s output is stable even if a page has an OCR-uncertain digit — see
Rule 14 for how that uncertainty surfaces.

---

### Rule 4 — Bullet and Numbered Lists

| | |
|---|---|
| Purpose | Preserve list type (bullet vs. numbered), item order, and nesting depth. |
| Reasoning | Distinct from clause numbering (Rule 3) — a list is enumerating items, not establishing referenceable structure. Losing the bullet/numbered distinction changes the document's meaning (a numbered list often implies sequence or priority that a bullet list does not). |
| Related pipeline stage | Block Classification (Stage 7), per-line prefix regex. |

**Example input**: A "Tenant Obligations" clause followed by four bullet points.

**Correct output**: `list` block, `attrs.listType: "bullet"`, containing four `listItem` children.

**Incorrect output**: Merging the four bullets into a single `paragraph` block with manual line
breaks — this is the single most common generic-OCR failure mode and is exactly what this
project's list-detection heuristic exists to prevent.

**Implementation notes**: A numbered list (`1)`, `2)`, `3)`...) is distinguished from Rule 3's
clause numbering by context: clause numbers appear at the *start* of a top-level or nested clause
and participate in the document's referenceable hierarchy; list numbering appears inside an
existing clause enumerating sub-items with no further nesting expected below it. Where this
distinction is genuinely ambiguous from layout alone, the pipeline defaults to `list` (the
lower-consequence choice — see "Things smallerDOCS must NEVER do" below).

---

### Rule 5 — Tables, Borders, Alignment, and Merged Cells

| | |
|---|---|
| Purpose | Reproduce table structure — row/column count, cell merges, and per-cell text — exactly, including cells that are visually empty. |
| Reasoning | Legal documents use tables for rent schedules, party information, exhibits, and signature blocks; misplacing even one cell's content silently corrupts data like a dollar amount or a date. |
| Related pipeline stage | Table Detection (Stage 8). |

**Example input**: A 2-column, 3-row rent schedule table with the header row's two cells merged
into one spanning cell reading "PAYMENT SCHEDULE".

**Correct output**: `table` block with 3 `tableRow` children; row 0 has a single `tableCell` with
`colSpan: 2`; rows 1–2 each have two ordinary cells.

**Incorrect output**: Flattening the table into paragraph text ("Payment Schedule: Month 1 —
$1,500, Month 2 — $1,500...") — this is explicitly forbidden even as a "best effort" fallback for
a table Table Detection *could* structure; the flattening fallback in `OCR_PIPELINE.md` Stage 8
is reserved only for tables the structure model genuinely fails on, and even then is flagged with
`confidence: 0.0`, never silently presented as equivalent to a properly structured table.

**Implementation notes**: Table borders and alignment are not stored as separate IDM fields —
border style is a purely visual property outside the IDM's structural scope (project vision:
structure over cosmetic appearance). Export always renders tables with a plain grid border
(`EXPORT_SYSTEM.md`: `"Table Grid"` style in DOCX, `border-collapse: collapse` in HTML) regardless
of the source table's original border style (bordered, borderless, or partial) — this is a
deliberate, documented simplification, not an oversight.

---

### Rule 6 — Signatures, Witness Blocks, Signature Lines, and Date Fields

| | |
|---|---|
| Purpose | Preserve the presence, position, and role labeling of signature-related content without inventing signatures that aren't there. |
| Reasoning | A blank signature line is meaningfully different from a filled one, and both are meaningfully different from no signature block at all — legal documents are frequently reconstructed *before* signing, and the reconstruction must not imply completion that hasn't happened. |
| Related pipeline stage | Layout Analysis (Stage 5, candidate detection) + Block Classification (Stage 7, role confirmation). |

**Example input**: A blank underscore line reading `"________________________"` followed by
`"Tenant Signature"` and `"Date: ___________"` beneath it.

**Correct output**: Two `signatureLine` blocks — one `attrs.role: "signatory"`, one
`attrs.role: "date"` — each preserving exactly the literal underscore/blank content present, not
converted to a form-field placeholder or removed.

**Incorrect output**: Detecting a blank signature line and omitting it as "empty content," or
conversely rendering it as filled/checked.

**Implementation notes**: `witness` and `notary` roles use the same block type with a different
`attrs.role`, matched by keyword adjacency ("Witness:", "Notary Public", "Sworn before me").

---

### Rule 7 — Forms, Checkboxes, and Initial Fields

| | |
|---|---|
| Purpose | Preserve checkbox state (checked/unchecked/indeterminate) and initial-field presence exactly as scanned. |
| Reasoning | A checked box and an unchecked box are opposite legal facts; misreading one as the other is a correctness failure far more serious than a misread word, since it can't be caught by reading the surrounding sentence for sense. |
| Related pipeline stage | Block Classification (Stage 7). |

**Example input**: A form clause with `☑ Option A` and `☐ Option B`.

**Correct output**: Two `listItem` blocks whose leading run's text literally includes the checked
(`☑`) or unchecked (`☐`) glyph as recognized — checkbox state is carried as literal text content,
not as a separate structured field in v1 (no dedicated `checkbox` block type exists in the v1 IDM;
this is a deliberate scope decision, not an oversight — see Implementation notes).

**Incorrect output**: Normalizing both to the same glyph, or omitting the glyph and leaving only
"Option A" / "Option B" as plain text — either destroys the recorded state.

**Implementation notes**: A checkbox glyph the OCR engine cannot confidently distinguish as
checked vs. unchecked is preserved as the ambiguous/best-guess glyph *with reduced confidence*
(Rule 14) rather than defaulted to unchecked — defaulting would be inventing a legal fact. Initial
fields (small blank boxes for per-page initials) are treated identically to signature lines
(Rule 6) — preserved as blank `signatureLine` blocks with `attrs.role: "signatory"` if unfilled.

---

### Rule 8 — Headers, Footers, Page Numbers, and Repeated Content

| | |
|---|---|
| Purpose | Keep running headers/footers and page numbers out of the main reading-order content, while still preserving that they exist and repeat. |
| Reasoning | A header repeating "CONFIDENTIAL — DRAFT" on every page must not appear 20 times interleaved into the body text of a 20-page contract; but its presence is still real document content that shouldn't vanish without a trace. |
| Related pipeline stage | Reading Order Detection (Stage 6, suppression + repeated-content detection). |

**Example input**: Every page footer reads `"Page {N} of 20 — Lease Agreement"`.

**Correct output**: Footer regions are suppressed from `Page.blocks` reading order on every page
(per `OCR_PIPELINE.md` Stage 6) but the *first* occurrence's normalized text is retained as
`Page.blocks` does not carry it at all in v1 — footers/headers are dropped from the visible,
editable document body entirely once confirmed repeated, since they are page-furniture, not
document content a user edits. This is a deliberate v1 simplification: full footer/header
round-tripping through the editor and back into export is listed as a `KNOWN_EDGE_CASE`, not a v1
guarantee.

**Incorrect output**: A "Page 3 of 20 — Lease Agreement" line appearing as a `paragraph` block
sitting between two unrelated clauses in the reconstructed body.

**Implementation notes**: This is the one case in this document where content is deliberately
*not* carried into the editable body — justified because footers/headers are, by definition,
outside the document's substantive content and reproducing them as interleaved body paragraphs
would actively corrupt reading order, which is a worse fidelity failure than omitting them from the
edit surface. This does not violate "never silently drop content" (Design Principles) because it
is a documented, visible, intentional exclusion — not a silent one — and is limited to *repeated*
header/footer content, not clauses that merely happen to sit near a page edge.

---

### Rule 9 — Blank Lines, Blank Pages, and Page Breaks

| | |
|---|---|
| Purpose | Preserve intentional blank space and page boundaries; never collapse them away as "empty content." |
| Reasoning | An entirely blank page in a legal document (common: "This page intentionally left blank" or simply blank between exhibits) is sometimes itself legally significant, and page boundaries matter for anyone cross-referencing the original by page number. |
| Related pipeline stage | Block Classification (Stage 7, synthetic `pageBreak` insertion). |

**Example input**: A 22-page lease where page 15 is entirely blank.

**Correct output**: Page 15 is still emitted as a `Page` object with `blocks: []` (or a single
`pageBreak` block), preserving the document's true page count and boundaries.

**Incorrect output**: Silently omitting page 15 from `pages[]`, making the document appear to be
21 pages.

**Implementation notes**: A `pageBreak` block is inserted between every pair of adjacent pages
unconditionally (per `OCR_PIPELINE.md` Stage 7's block type table) — this is what the editor
renders as its page-break marker (`EDITOR_SPECIFICATION.md`) and what export uses to call
`document.add_page_break()` (`EXPORT_SYSTEM.md`).

---

### Rule 10 — Character-Level Formatting (Bold, Italic, Underline, Capitalization)

| | |
|---|---|
| Purpose | Preserve exactly the bold/italic/underline marks and capitalization present in the source — never add emphasis that wasn't there, never remove emphasis that was. |
| Reasoning | Capitalization and emphasis in legal documents are frequently substantive, not stylistic — e.g. defined terms are conventionally capitalized ("the **Premises**", "**Tenant**") specifically to signal they carry a specific defined meaning elsewhere in the document; silently lowercasing them removes that signal. |
| Related pipeline stage | Formatting Reconstruction (Stage 9). |

**Example input**: `"...as defined in the LEASE AGREEMENT, the TENANT shall..."`.

**Correct output**: Text reproduced with identical capitalization: `"LEASE AGREEMENT"`,
`"TENANT"` exactly as scanned.

**Incorrect output**: "Cleaning up" the text to sentence case because it reads as shouting — this
is exactly the kind of cosmetic "improvement" this project must never make (see "Things
smallerDOCS must NEVER do" below).

**Implementation notes**: Bold/italic/underline detection rules and their conservative
false-positive avoidance are specified in `OCR_PIPELINE.md` Stage 9. Capitalization requires no
detection step at all — recognized characters are emitted exactly as recognized, uppercase and
lowercase alike; there is no normalization step anywhere in the pipeline that could alter case.

---

### Rule 11 — Whitespace Preservation

| | |
|---|---|
| Purpose | Preserve meaningful whitespace (multiple spaces used for tabular alignment in non-table content, e.g. a simple key-value list) without introducing spurious whitespace OCR artifacts. |
| Reasoning | Some legal documents use plain-text spacing (not real tables) to align short key-value pairs (e.g. "Landlord: ___" / "Tenant: ___" side by side); collapsing runs of spaces to one loses that visual pairing, while OCR occasionally introduces spurious double-spaces that shouldn't be preserved as meaningful. |
| Related pipeline stage | Formatting Reconstruction (Stage 9). |

**Example input**: `"Landlord:    John Smith"` where the extra spacing is deliberate visual
alignment, not a real table.

**Correct output**: The run text preserves the space run as recognized by OCR (word-level bboxes
naturally reflect real gaps; multiple detected words with a large horizontal gap between them are
rendered as a single space in v1 — see Implementation notes for the limitation this implies).

**Incorrect output**: Collapsing all inter-word whitespace to exactly one space always, destroying
any visual key-value alignment the source relied on.

**Implementation notes**: v1 does not attempt to reconstruct exact multi-space runs as literal
repeated space characters (Word/HTML rendering collapses runs of plain spaces visually regardless,
per standard whitespace-collapsing behavior in both DOCX and HTML) — where alignment fidelity
genuinely matters, the source almost always uses a real table structure (Rule 5) or explicit tab
stops, which *are* preserved structurally. This is a documented, narrow limitation, not a silent
one.

---

### Rule 12 — Reading Order (Multi-Column, Table Interleaving)

| | |
|---|---|
| Purpose | Reconstruct the single correct linear reading sequence, even across multi-column layouts or pages where tables are interspersed with paragraph text. |
| Reasoning | An out-of-order reconstruction is worse than a merely imperfectly-formatted one — it can invert cause and effect between clauses or attach an obligation to the wrong party. |
| Related pipeline stage | Reading Order Detection (Stage 6) — full algorithm specified in `OCR_PIPELINE.md`. |

**Example input**: A two-column exhibit list followed by a single-column signature page.

**Correct output**: All of column 1 (top to bottom), then all of column 2, then the signature page
content — never row-by-row across both columns.

**Incorrect output**: Reading left-to-right straight across both columns, which is how a naive
top-to-bottom, left-to-right sort (ignoring column boundaries) would fail.

**Implementation notes**: This rule is fully delegated to the XY-cut algorithm in `OCR_PIPELINE.md`
Stage 6 — no additional legal-specific logic is layered on top; reading order is a general
document-structure concern, not a legal-specific one.

---

### Rule 13 — Multi-Page Document Continuity

| | |
|---|---|
| Purpose | Preserve a clause or paragraph that spans a page boundary as one continuous block, not two disconnected fragments. |
| Reasoning | Legal clauses routinely run across a page break; splitting them into two unrelated paragraphs breaks both readability and any downstream text search/analysis. |
| Related pipeline stage | Reading Order Detection (Stage 6, cross-page continuation check). |

**Example input**: A paragraph's last line sits at the very bottom of page 4 with no terminal
punctuation, and page 5 begins with a lowercase continuation of the same sentence.

**Correct output**: A single `paragraph` block whose `runs` concatenate both pages' text, with a
`pageBreak` block still inserted immediately before it in the page sequence to preserve the fact
that a physical page boundary exists there (Rule 9) — continuity of content and preservation of
page boundaries are not in conflict; both are recorded.

**Incorrect output**: Two separate `paragraph` blocks, the second starting mid-sentence with a
lowercase word, with no indication they're one continuous clause.

**Implementation notes**: Continuation is detected via: the top-of-page-5 line begins with a
lowercase letter or a conjunction, *and* the bottom-of-page-4 line has no terminal punctuation
(`.`, `;`, `:`) and is not a `clauseNumber`-initiated line. Both conditions must hold — this is
deliberately conservative to avoid incorrectly merging two genuinely separate paragraphs that
happen to fall at a page boundary.

---

### Rule 14 — OCR Uncertainty and Confidence Preservation

| | |
|---|---|
| Purpose | Never resolve OCR ambiguity by guessing — always retain and expose the actual confidence of every recognized span. |
| Reasoning | A misread digit in a dollar amount or a date is a correctness failure with real consequences; the system must make its own uncertainty visible rather than presenting a guess with the same authority as a confident read. |
| Related pipeline stage | Confidence Handling, fully specified in `OCR_PIPELINE.md`. |

**Example input**: A degraded scan where "$1,500.00" is only 80% legible on the final zero.

**Correct output**: The run's text is the model's best single reading (`"$1,500.00"`) with
`confidence: 0.82` (illustrative), not multiple candidate readings and not a rounded/"safe" value
substituted for the actual OCR output.

**Incorrect output**: Silently defaulting the confidence to a fixed value, or "correcting" the
digit to a rounder number because it looks more plausible.

**Implementation notes**: The full confidence-band table and its propagation rules
(`Block.confidence` = min of constituent `Run.confidence`) live in `OCR_PIPELINE.md`. This rule
exists here specifically to state the legal-document-specific *reasoning* for why that mechanism
is non-negotiable: financial figures, dates, and party names are exactly the content categories
where an undetected misread carries real-world consequence.

---

### Rule 15 — User-Edited Blocks

| | |
|---|---|
| Purpose | Once a user edits reconstructed content in the editor, that edit is authoritative and is never silently reverted, re-inferred, or blended with the original OCR reading. |
| Reasoning | The whole point of the editor is to let a human correct exactly the kind of OCR uncertainty Rule 14 preserves — the system must fully defer to that correction. |
| Related pipeline stage | N/A (post-pipeline) — governed by `EDITOR_SPECIFICATION.md`'s reverse mapping. |

**Example input**: A user corrects a low-confidence OCR read of "$1,5OO.OO" to "$1,500.00" in the
editor.

**Correct output**: On export, the corrected text is used verbatim; `confidence` for that block is
reset to `1.0` (per `EDITOR_SPECIFICATION.md`'s reverse-mapping rule), signaling it is now
human-verified.

**Incorrect output**: Re-running OCR confidence scoring against the edited text, or preserving the
original low-confidence flag alongside the correction in a way that casts doubt on the user's
fix.

**Implementation notes**: This rule is what makes Rule 14's non-guessing stance safe rather than
merely cautious — the system doesn't need to guess, because the editor exists precisely so a human
can resolve every flagged uncertainty deliberately.

---

### Rule 16 — Export Consistency

| | |
|---|---|
| Purpose | The DOCX and HTML exports must reflect exactly the document state visible in the editor at export time — no drift between what the user sees and what they download. |
| Reasoning | A lawyer reviewing a reconstructed contract on screen and then sending the exported .docx to a counterparty must be able to trust the two are identical; any silent divergence is a serious trust failure for a tool whose entire purpose is document fidelity. |
| Related pipeline stage | N/A — governed by `EXPORT_SYSTEM.md`. |

**Example input**: A user has applied bold to a phrase and merged two table cells in the editor,
then exports to DOCX.

**Correct output**: The exported DOCX shows the same bold phrase and the same merged cells,
because export is driven by the current Tiptap document content posted at export time
(`API_SPECIFICATION.md`'s `POST /export`), not by a stale copy of the original pipeline output.

**Incorrect output**: Export regenerating from the original IDM (pre-edit) rather than the
currently edited document — this would silently discard every edit the user made.

**Implementation notes**: This is why `EXPORT_SYSTEM.md` mandates a single server-side conversion
path (`tiptap_to_idm.py`) fed by the *posted* editor content, rather than two independently
maintained serializers that could drift from each other or from the live editor state.

---

### Rule 17 — Comparison Mode Consistency

| | |
|---|---|
| Purpose | Every block a user can click in either comparison pane must resolve to the correct corresponding region in the other pane, for as long as that block traces back to the original scan. |
| Reasoning | Comparison Mode's entire value is letting a user verify the reconstruction against the source at a glance — a broken or drifting mapping defeats that purpose and could let an error go unnoticed. |
| Related pipeline stage | N/A — governed by `DATA_FLOW.md`'s click-to-highlight flow and `EDITOR_SPECIFICATION.md`'s `sourceBlockId` mark. |

**Example input**: A user clicks a clause in the editor pane.

**Correct output**: The corresponding region of the original scan highlights, using the same
`Block.id` assigned once in `Formatting Reconstruction` (`OCR_PIPELINE.md` Stage 9) and carried
unchanged through `idmToTiptap.ts` as `sourceBlockId`.

**Incorrect output**: The highlight lands on the wrong region, or nothing happens, because a
block's id was regenerated somewhere along the pipeline instead of being assigned once and
preserved.

**Implementation notes**: Blocks with no source (user-created new content, `sourceBlockId: null`
per `EDITOR_SPECIFICATION.md`) are correctly non-interactive in this direction — this is not a
violation of the rule, since there is no original-scan region for them to correspond to.

---

## Things smallerDOCS must NEVER do

- **Never invent missing text.** If a word cannot be read, the best-effort literal reading is
  emitted with low confidence (Rule 14) — never a plausible substitute.
- **Never correct spelling automatically.** A misspelling in the source document is part of the
  source document; auto-correcting it silently changes the legal text.
- **Never rewrite legal language.** No stage may paraphrase, simplify, or "clean up" phrasing for
  readability — smallerDOCS reconstructs, it does not edit content.
- **Never renumber clauses.** Clause numbers are reproduced literally (Rule 3), never
  auto-generated or resequenced, even if a number appears to be skipped or out of order in the
  source — an apparent gap might be intentional (e.g. a clause removed during drafting) and is not
  smallerDOCS's decision to "fix."
- **Never merge separate clauses.** Two adjacent but distinct numbered clauses are always kept as
  distinct blocks, even if visually close together.
- **Never flatten tables.** Table structure is preserved (Rule 5) except in the narrow, explicitly
  flagged fallback case where structure recognition genuinely fails — and even then the
  degradation is visible via `confidence: 0.0`, never presented as equivalent to success.
- **Never remove blank pages.** A blank page is preserved as an empty `Page` (Rule 9).
- **Never change capitalization.** Case is reproduced exactly (Rule 10).
- **Never "improve" formatting.** No stage makes a subjective aesthetic judgment about how the
  document *should* look; every formatting decision traces back to evidence in the source.
- **Never infer information that is not present.** Every field, mark, and structural claim in the
  IDM must be traceable to something actually observed in the source document or the OCR/layout
  model's direct output — not filled in from a template or a document-type assumption.
- **When uncertain, preserve uncertainty instead of guessing.** This is the umbrella principle
  behind Rules 7, 8, and 14 specifically, and behind every default-to-the-safer-option decision
  documented throughout this file and `OCR_PIPELINE.md`.

---

## Project Philosophy

**smallerDOCS reconstructs legal documents. It does not rewrite them.**

Every implementation decision — in this document, in `OCR_PIPELINE.md`, and in every stage of the
pipeline those two documents together define — is subordinate to this one sentence. When a
decision has to be made between structural correctness and cosmetic polish, correctness wins. When
a decision has to be made between a confident guess and a flagged uncertainty, the flagged
uncertainty wins. When a decision has to be made between preserving something the source document
actually contains and improving on it, preservation wins, every time, without exception.

The product's value to a lawyer, a law firm, or a business is not that it produces a
beautiful document — it's that it produces a *trustworthy* one: an editable version they can
believe reflects exactly what the original said, with every point of remaining uncertainty made
visible rather than smoothed over. Faithfulness to the source is not one design goal among several
for smallerDOCS. It is the product.

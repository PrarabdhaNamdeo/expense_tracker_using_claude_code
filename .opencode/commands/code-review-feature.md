---
description: Runs parallel security and quality code
  review for a specific Spendly feature. Pass the spec
  name or path e.g. /code-review-feature 03-login
allowed-tools: Bash(git diff), Bash(git diff --staged)
---

Run the full code review pipeline for the feature
specified by $ARGUMENTS.

If no argument is provided, stop immediately and say:
"Please provide a spec name. Usage: /code-review-feature <spec-name> e.g. /code-review-feature 03-login"

## Resolve paths

Before any other step, normalise $ARGUMENTS into a single spec stem:

1. Trim whitespace and surrounding quotes.
2. Replace backslashes (`\`) with forward slashes (`/`) for parsing only.
3. Remove a trailing `.md` (case-insensitive) if present.
4. If the remaining value contains `/`, keep only the part after the final `/`.
   This accepts a plain name, `.opencode/specs/<name>`, an absolute Windows
   path, and paths using either slash direction.
5. Trim again. If the stem is empty, stop with the "Please provide a spec name" message above.

Use these resolved values everywhere below:

- `<SPEC_NAME>` = the stem from step 4 (e.g. `03-login-and-logout`)
- `<SPEC_FILE>` = `.opencode/specs/<SPEC_NAME>.md` (always forward slashes)

If `<SPEC_FILE>` does not exist, stop immediately and say:
"Spec file not found at .opencode/specs/<SPEC_NAME>.md. Please check the spec name and try again."

## Pre-flight Check

Before invoking any subagents, collect the diff:
- Run `git diff` for unstaged changes
- Run `git diff --staged` for staged changes
- Combine both into a single diff

If both are empty, stop immediately and say:
"No changes detected. Implement the feature before
running code review."

---

## Step 1: Parallel Review

Invoke both subagents simultaneously with the same
context:

**spendly-security-reviewer** receives:
- The combined diff from the pre-flight check
- Spec file for context: `<SPEC_FILE>`
- Source files to reference: `app.py` and
  `database/` directory
- Instruction: Review only the changed code for
  security vulnerabilities. Do not comment on quality
  or style.

**spendly-quality-reviewer** receives:
- The combined diff from the pre-flight check
- Spec file for context: `<SPEC_FILE>`
- Source files to reference: `app.py`, `database/`
  directory, and `templates/` directory
- Instruction: Review only the changed code for quality,
  Flask best practices, and maintainability. Do not
  comment on security concerns.

Both subagents must run in parallel. Do not wait for
one to finish before starting the other.

---

## Step 2: Unified Report

Once both subagents have completed, combine their
findings into a single unified report. De-duplicate
any overlapping findings — if both agents flagged the
same line for different reasons, merge them into one
finding with both perspectives noted.

Structure the combined report as:
Code Review Report — <SPEC_NAME>
Security Findings
[spendly-security-reviewer output]
Quality Findings
[spendly-quality-reviewer output]
Combined Action Plan
Ordered checklist of everything that needs to be fixed,
prioritized by severity:

[Critical/High security findings first]
[Quality CHANGES REQUESTED items second]
[Medium/Low security findings third]
[Quality APPROVED WITH SUGGESTIONS items last]

Overall Verdict
APPROVED — ready to commit
APPROVED WITH SUGGESTIONS — can commit, address
suggestions in future steps
CHANGES REQUESTED — must fix before committing,
see action plan above
---

## Step 3: Ask for Approval

After presenting the unified report, ask:

"Do you want me to implement the action plan now?"

Wait for explicit user confirmation before making
any changes. Do not touch any files until the user
approves.

---

## Rules
- Do NOT edit any files before user approval
- Do NOT start one reviewer before the other —
  both must run in parallel
- Do NOT skip the pre-flight diff check
- Do NOT proceed if the spec file at `<SPEC_FILE>` does not exist —
  report it and stop
- If either subagent fails or returns no output,
  report it and do not present a partial review
  as complete

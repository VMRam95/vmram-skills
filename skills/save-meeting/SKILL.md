---
name: save-meeting
description: |
  Save and analyze meeting transcripts/notes automatically into project memory.
  Extracts key decisions, action items, blockers, and impacts.
  Trigger phrases: "meeting", "reunion", "save meeting", "guardar reunion", "te paso la reunion", "notas de reunion", "/save-meeting"
---

# Save Meeting

Analyze a meeting transcript and save structured notes to project memory.

## Arguments

```
/save-meeting [topic]
```

| Argument | Description | Required |
|----------|-------------|----------|
| topic | Optional short label for the meeting (e.g., "architecture", "sprint-planning") | No (auto-detected) |

## Workflow

### 1. Detect meeting content

The user will paste a meeting transcript (raw text, audio transcription, or summary). It may be:
- Raw audio transcription (messy, with filler words)
- Structured meeting notes
- Chat/email thread
- Mix of Spanish and English

### 2. Analyze and extract

From the transcript, extract ALL of the following:

#### Key Decisions
- What was decided? By whom?
- What was rejected and why?

#### Action Items
- Who needs to do what?
- What's blocked and on whom?

#### Open Questions
- What remains undecided?
- What needs further investigation?

#### Architecture/Technical Impact
- Changes to components, naming, structure
- New constraints or conventions discovered
- Things that affect current codebase or CLAUDE.md

#### Project Context
- People mentioned and their roles
- External systems or teams referenced
- Timeline or deadline info

### 3. Save to memory

**File**: Save to the CURRENT PROJECT's memory directory:
- Path pattern: `memory/meeting-YYYY-MM-DD-{topic}.md`
- If a meeting file for the same date+topic already exists, append or update it

**Format**:
```markdown
# Meeting YYYY-MM-DD — {Topic}

## Status: {PENDING/RESOLVED/INFORMATIONAL}

## Participants
- Name (role if known)

## Key Decisions
1. Decision — rationale

## Action Items
| Item | Owner | Status |
|------|-------|--------|
| ... | ... | PENDING/BLOCKED/DONE |

## Open Questions
- Question — context

## Technical Impact
| Topic | Action | Status |
|-------|--------|--------|
| ... | ... | BLOCKED/PENDING/NO CHANGE |

## Raw Notes
{Condensed but faithful summary of the discussion, preserving important nuances}
```

### 4. Update MEMORY.md

Add or update a reference in the project's `MEMORY.md`:
- Add a line under a `## Meeting Notes` section (create if missing)
- Format: `- YYYY-MM-DD {topic}: see \`meeting-YYYY-MM-DD-{topic}.md\` — {one-line summary}`
- Keep MEMORY.md concise — details go in the meeting file

### 5. Confirm to user

After saving, respond with:
- One-line confirmation that it's saved
- Path to the meeting file
- Count of decisions / action items / open questions extracted
- DO NOT dump the full analysis unless user asks

## Rules

- **NEVER apply code changes** based on meeting content — only save notes
- **Preserve nuance** — if someone disagreed, note the disagreement
- **Spanish is OK** — meetings will often be in Spanish, save in the language that makes sense (Spanish for SLU-specific terms, English for technical)
- **Be faithful** — don't invent decisions that weren't made, mark unclear items as "Open Questions"
- **Idempotent** — if user pastes the same meeting twice, update don't duplicate
- **Date**: use today's date unless the user specifies otherwise

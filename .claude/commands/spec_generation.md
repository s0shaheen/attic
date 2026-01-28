# Spec Generation Skill

## Overview

This skill generates production-grade task specification documents from a PRD (Product Requirements Document) and MVP Guide. It transforms high-level epic/task breakdowns into detailed, implementable specifications.

---

## When to Use

Use this skill when you need to:
- Generate a single task spec from PRD + MVP Guide
- Generate all specs for an entire epic
- Batch generate specs for multiple epics

---

## Required Context Files

Before generating specs, ensure you have access to:

1. **PRD Document** — Contains:
   - Feature requirements (F1, F2, etc.)
   - Data models (SQL schemas)
   - API contracts
   - Non-functional requirements
   - User stories and acceptance criteria

2. **MVP Guide** — Contains:
   - Epic breakdown
   - Task list per epic
   - Dependencies between tasks
   - Implementation order

3. **Task Spec Template** — The standardized format (see `attic/tasks/TASK_SPEC_TEMPLATE.md`)

---

## Generation Workflow

### Step 1: Analyze the Task Context

```
Read the MVP_GUIDE.md to identify:
- Epic name and description
- Task ID and name
- Task description
- Dependencies (upstream and downstream)
```

### Step 2: Extract PRD Requirements

```
From the PRD, extract for this task:
- Relevant Feature section (F1-F8)
- User story
- Acceptance criteria
- Data model (if applicable)
- API contracts (if applicable)
- Non-functional requirements
- Security considerations
```

### Step 3: Synthesize Technical Design

```
Based on PRD + MVP Guide + codebase conventions:
- Define component architecture
- Design interfaces/protocols
- Specify file structure
- Identify external dependencies
- Design test strategy
```

### Step 4: Generate the Spec

```
Fill in the template with:
- All extracted requirements
- Technical specifications
- Acceptance criteria (make them specific and testable)
- Security and observability requirements
```

---

## Claude Code Prompts

### Generate Single Task Spec

```
Generate a production-grade task specification for Task [EPIC.TASK]: [TASK_NAME]

Context:
- PRD: @docs/Attic_MVP_PRD_v1.0.1.md
- MVP Guide: @tasks/MVP_GUIDE.md  
- Template: @tasks/TASK_SPEC_TEMPLATE.md
- Example: @tasks/EXAMPLE_SPEC_3.4_APIFY_ENRICH.md (for reference)

Requirements:
1. Extract all relevant requirements from PRD section [F#]
2. Include complete API contracts with request/response schemas
3. Include SQL for any data model changes
4. Define Python protocol interfaces for any new capabilities
5. Make acceptance criteria specific and testable
6. Include realistic test cases (happy path, edge cases, errors)
7. Add security considerations specific to this task
8. Define logging events and metrics for observability

Output:
- Save to: tasks/[epic-folder]/[task-id]-[task-name-slug].md
- Use kebab-case for filenames
- Follow the exact template structure
```

### Generate All Specs for an Epic

```
Generate production-grade task specifications for all tasks in Epic [N]: [EPIC_NAME]

Context:
- PRD: @docs/Attic_MVP_PRD_v1.0.1.md
- MVP Guide: @tasks/MVP_GUIDE.md
- Template: @tasks/TASK_SPEC_TEMPLATE.md
- Example: @tasks/EXAMPLE_SPEC_3.4_APIFY_ENRICH.md

For each task in Epic [N]:
1. Create a detailed spec following the template
2. Ensure cross-references between dependent tasks are accurate
3. Verify API contracts are consistent across related tasks
4. Ensure data model changes don't conflict

Output structure:
tasks/
└── [n]-[epic-slug]/
    ├── [n].1-[task-slug].md
    ├── [n].2-[task-slug].md
    └── ...

After generating all specs, create an EPIC_SUMMARY.md that:
- Lists all tasks with their status
- Shows dependency graph
- Highlights any open questions or conflicts
```

### Validate Spec Completeness

```
Review the task specification at @tasks/[path] for completeness and quality.

Check for:
1. All template sections are filled (no "[placeholder]" text remaining)
2. Requirements are specific and testable (no vague language)
3. API contracts include all fields with types
4. Acceptance criteria are binary (pass/fail determinable)
5. Dependencies reference actual task IDs that exist
6. Security section addresses auth, authz, validation, PII
7. Test cases cover happy path, edge cases, and errors
8. Metrics have reasonable alert thresholds

Output:
- List of missing or incomplete sections
- Suggestions for improvement
- Overall completeness score (0-100%)
```

---

## Quality Checklist

A good spec should pass these checks:

### Requirements Quality
- [ ] Each requirement has a unique ID (FR-1, NFR-1, etc.)
- [ ] Requirements use "must", "should", "could" priority
- [ ] No ambiguous language ("fast", "user-friendly", "easy")
- [ ] Metrics have specific targets (e.g., "< 500ms", "≥ 99.5%")

### Technical Completeness
- [ ] Data model includes all fields, types, indexes
- [ ] API contracts include all endpoints, methods, params
- [ ] Error responses are enumerated with codes
- [ ] File structure matches project conventions

### Testability
- [ ] Each acceptance criterion is binary (pass/fail)
- [ ] Test cases have specific inputs and expected outputs
- [ ] Edge cases and error scenarios are covered
- [ ] Integration test scenarios are defined

### Dependencies
- [ ] All upstream dependencies listed with blocking status
- [ ] Downstream dependents identified
- [ ] External package versions specified
- [ ] No circular dependencies

### Security & Observability
- [ ] Auth/authz approach specified
- [ ] Input validation approach defined
- [ ] PII handling documented
- [ ] Logging events defined with levels and fields
- [ ] Metrics defined with alert thresholds

---

## Example Usage Session

```bash
# Start Claude Code in project root
cd ~/projects/attic
claude

# Generate a single spec
> Generate a production-grade task specification for Task 3.7: WHISPER_TRANSCRIBE step
> 
> Context:
> - PRD: @docs/Attic_MVP_PRD_v1.0.1.md
> - MVP Guide: @tasks/MVP_GUIDE.md
> - Template: @tasks/TASK_SPEC_TEMPLATE.md
>
> This task handles audio transcription when TikTok subtitles aren't available.
> Reference the APIFY_ENRICH spec for style: @tasks/3-pipeline/3.4-apify-enrich.md

# Generate all specs for an epic
> Generate all task specs for Epic 1: Authentication
> Save to tasks/1-auth/

# Validate a spec
> Review @tasks/3-pipeline/3.7-whisper-transcribe.md for completeness
```

---

## Customization

### Adjusting Detail Level

For simpler tasks (Low complexity), you can reduce:
- Component Design section (minimal)
- Observability section (basic logging only)
- Rollout Plan (simple on/off)

For complex tasks (High complexity), expand:
- Architecture diagrams (multiple views)
- Sequence diagrams for flows
- More detailed error handling matrix
- Phased implementation approach

### Project-Specific Conventions

Update this skill with your project's:
- File naming conventions
- Module structure patterns
- Preferred testing frameworks
- Logging/metrics standards
- Security requirements

---

## Anti-Patterns to Avoid

1. **Vague Requirements**: "The system should be fast" → "Response time < 200ms p95"

2. **Missing Error Handling**: Always enumerate error cases and their handling

3. **Orphan Tasks**: Every task should have clear upstream/downstream deps

4. **Untestable Criteria**: "User experience should be good" → "Task completes in < 3 clicks"

5. **Copy-Paste Specs**: Each spec should be tailored; don't copy generic sections

6. **Missing Security**: Every spec needs auth/authz/validation consideration

7. **No Observability**: Every spec needs logging and metrics for production debugging
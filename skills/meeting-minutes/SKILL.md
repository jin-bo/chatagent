---
name: meeting-minutes
description: Generate structured meeting minutes from meeting notes and chat records. Use this skill when users ask to summarize meetings, create meeting minutes, organize meeting notes, or document meeting outcomes. Supports extracting meeting information, participants, discussion points, decisions, action items, and to-do lists. Outputs in Markdown format with clear structure and actionable items.
---

# Meeting Minutes Generator

Generate professional, well-structured meeting minutes from meeting notes, chat records, or transcripts.

## Overview

This skill transforms unstructured meeting content into organized meeting minutes with:

1. Meeting basic information (time, location, participants)
2. Discussion points organized by topics
3. Clear decisions made
4. Actionable items with owners and deadlines
5. Follow-up to-do items

## Workflow

Follow these steps to generate meeting minutes:

### Step 1: Analyze Input Content

Review the provided meeting notes or chat records to identify:

- Meeting context (time, participants, purpose)
- Main discussion topics and key points
- Decisions made during the meeting
- Action items with potential owners
- Outstanding questions or follow-ups

### Step 2: Extract Meeting Information

Identify and extract:

- **Meeting topic/title**: Infer from content if not explicitly stated
- **Meeting time**: Extract or ask user if not provided
- **Meeting location**: Physical location or online platform (e.g., Zoom, Teams)
- **Participants**: Names and roles (extract from content or ask user)
- **Recorder**: Usually the person creating the minutes (can ask user)

### Step 3: Organize Discussion Points

Structure discussion content by:

- Grouping related topics together
- Using descriptive topic headings (level 3 headings)
- Summarizing key points concisely
- Preserving important data, facts, and different viewpoints
- Removing redundant or off-topic content

### Step 4: Identify Decisions

Extract clear decisions made during the meeting:

- State each decision clearly and actionably
- Include rationale if mentioned
- Use bold text for decision topics
- Number decisions for easy reference

### Step 5: Extract Action Items

Create a structured action items table with:

- **序号** (Number): Sequential numbering
- **任务描述** (Task Description): Specific, measurable tasks
- **负责人** (Owner): Single person responsible (extract from content or mark as "待定" if unclear)
- **截止时间** (Deadline): Specific dates (extract from content or mark as "待定" if not specified)
- **状态** (Status): Always set to "待办" (To-do) initially

### Step 6: Identify To-Do Items

List items that need follow-up but don't have clear owners or deadlines:

- Questions requiring clarification
- Topics for next meeting
- Items pending external input

### Step 7: Format Output

Generate the meeting minutes following the standard template structure. See [template.md](references/template.md) for detailed format specifications and examples.

## Output Requirements

**Required sections:**
1. Meeting basic information (title, time, location, recorder)
2. Participants list
3. Discussion points (organized by topics)
4. Decisions made
5. Action items table

**Optional sections:**
6. Meeting agenda (if applicable)
7. To-do items (if applicable)
8. Notes (if applicable)

**Format standards:**
- Use Markdown formatting throughout
- Clear heading hierarchy (H1 for title, H2 for sections, H3 for sub-topics)
- Use tables for action items with proper alignment
- Use bold text to emphasize key decisions and topics
- Use consistent date format: YYYY-MM-DD HH:MM
- Keep language concise and professional

## Handling Missing Information

When critical information is missing:

- **Participants or roles**: Use names from content; mark roles as "参会者" if unclear
- **Meeting time**: Ask user or mark as "待确认"
- **Action item owners**: Mark as "待定" if not specified in content
- **Deadlines**: Mark as "待定" if not mentioned
- **Meeting location**: Mark as "待确认" if not stated

Always generate a complete meeting minutes document even with missing details. Mark unclear items appropriately rather than omitting sections.

## Best Practices

1. **Be concise**: Extract key information, avoid verbatim transcription
2. **Stay neutral**: Present facts and decisions objectively
3. **Be specific**: Use concrete language for action items
4. **Maintain structure**: Follow the standard template consistently
5. **Clarify ownership**: Each action item should have a single owner
6. **Set clear deadlines**: Action items need specific target dates
7. **Capture decisions**: Highlight what was decided, not just discussed
8. **Note disagreements**: Record significant different viewpoints when relevant

## Examples

For detailed format examples and complete meeting minutes samples, see [template.md](references/template.md).

## Template Reference

For complete format specifications, section requirements, and a full example, read [template.md](references/template.md) before generating meeting minutes.

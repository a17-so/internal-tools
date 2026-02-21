# Reddit Commenter - Batch Mode

> Executed when "Fill today's quota" command given
> See SKILL.md for single comment workflow

---

## Batch Execution Trigger

Start batch mode with these commands:
- "Fill today's quota"
- "Consume all remaining quota"
- "Run in batch mode"

---

## Pre-Start Check

```
1. Check tracking/reddit/today's-date.md (create from template.md if missing)
2. Check current comment count by subreddit
3. Calculate remaining quota:
   - Total 24 (8 subreddits × 3)
   - Subtract today's written comments
   - Remaining quota = 24 - Today's written comments
```

---

## Batch Workflow

```
[Start]
    ↓
[1] Check tracking file (/tracking/reddit/(today's date).md) → Calculate remaining quota
    ↓
[2] Select subreddit under quota (by priority criteria)
    ↓
[3] Start comment writing loop for that subreddit
    ↓
    [3-1] Execute SKILL.md Step 1-8 (write single comment)
    ↓
    [3-2] Update tracking file
    ↓
    [3-3] Report progress
    ↓
    [3-4] Check that subreddit's quota
          - Under 3 → back to [3-1]
          - Completed 3 → to [4]
          - No suitable posts → to [4]
    ↓
[4] Move to next subreddit (wait 5-15 minutes)
    ↓
[5] Check overall termination condition
    ↓
    YES → [End]
    NO  → Return to [2]
```

---

## Subreddit Selection Priority

| Priority | Criteria | Reason |
|----------|----------|--------|
| 1 | Subreddits with 0 activity today | Ensure variety |
| 2 | Subreddits with oldest last activity time | Distributed activity |
| 3 | Subreddits with available quota | Efficiency |

---

## Wait Time Rules

| Situation | Wait Time |
|-----------|-----------|
| Between comments in same subreddit | None |
| Between subreddit transitions | 5-15 minutes |
| Can't find suitable post | Move to next subreddit (wait 5-15 minutes) |

### Execution Example

```
Start r/WebDev
  → Comment 1/3 written
  → Comment 2/3 written
  → Comment 3/3 written ✓
  
r/WebDev complete → Wait 12 min → Move to r/ClaudeAI

Start r/ClaudeAI
  → Comment 1/3 written → Wait 6 min
  → Comment 2/3 written → Wait 8 min
  → Comment 3/3 written ✓
  
r/ClaudeAI complete → Wait 10 min → Move to r/Cursor
```

---

## Termination Conditions

Batch execution terminates when one of the following is met:

1. **Quota complete**: All subreddit quotas complete (24)
2. **No posts**: No suitable posts in all subreddits
3. **User interruption**: User requests stop
4. **Error occurred**: After 3 consecutive failures

---

### Progress Report
```
---
[Overall Progress] 6/24 completed

Completed subreddits:
✓ r/WebDev: 3/3
✓ r/ClaudeAI: 3/3

In progress:
→ r/Cursor: 0/3 (current)

Waiting:
- r/LocalLLaMA: 0/3
- r/ChatGPT: 0/3
- r/SideProject: 0/3
- r/Obsidian: 0/3
- r/Rag: 0/3

Next: Move to r/LocalLLaMA after r/Cursor quota complete
---
```

## Skip Conditions

When skipping specific subreddit:

**No suitable posts in New/Rising**: Skip if none after reviewing 5 posts

When skipping, report:
```
r/LocalLLaMA skipped - No suitable posts
→ Moving to r/ChatGPT
```

---

## Error Handling

| Error | Response |
|-------|----------|
| Page loading failure | Wait 30s then retry (max 3 times) |
| Comment posting failure | Move to next post |
| Login session expired | Stop batch, notify user |
| Rate limit detected | Wait 30 min then resume |

---

## Batch Completion Report

```
---
## Batch Completion Report

**Total Written**: 18/24
**Time Spent**: 2 hours 35 minutes

### Results by Subreddit
| Subreddit | Written | Skip Reason |
|-----------|---------|-------------|
| r/WebDev | 3/3 | - |
| r/ClaudeAI | 3/3 | - |
| r/Cursor | 2/3 | No suitable posts |
| r/LocalLLaMA | 0/3 | All skipped (no technical discussion) |
| r/ChatGPT | 3/3 | - |
| r/SideProject | 3/3 | - |
| r/Obsidian | 2/3 | No suitable posts |
| r/Rag | 2/3 | No suitable posts |

### Potential Customers Discovered
- 2 (updated in leads/reddit.md)

### Special Notes
- r/LocalLLaMA: All skipped due to no technical discussion posts today
---
```



> Single comment workflow (Step 1-8): See SKILL.md
> Personalization review: See resources/personalization_reddit.md

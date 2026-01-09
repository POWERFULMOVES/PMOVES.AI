# Complete Work Item

Mark a work item as completed after finishing the implementation.

## Arguments

- `$ARGUMENTS` - Required: work_item_id to complete

## Instructions

1. **Parse work item ID**:
   ```bash
   WORK_ITEM_ID="${ARGUMENTS}"
   if [ -z "$WORK_ITEM_ID" ]; then
     echo "Error: work_item_id is required"
     echo "Usage: /workitems:complete <work_item_id>"
     exit 1
   fi
   ```

2. **Verify ownership**:
   - Confirm work item is assigned to current BoTZ
   - Confirm status is 'in_progress'

3. **Gather completion metadata**:
   - Get latest commit SHA if available
   - Get PR URL if created
   - List files modified/created

4. **Complete the work item**:
   ```sql
   SELECT complete_work_item(
     '$WORK_ITEM_ID'::uuid,
     '$BOTZ_ID'::uuid,
     '$COMMIT_SHA',
     '$PR_URL',
     '$FILES_MODIFIED'::jsonb,
     '$FILES_CREATED'::jsonb
   );
   ```

5. **Clean up TAC worktree** (if applicable):
   ```bash
   if [ -n "$TAC_WORKTREE" ]; then
     echo "TAC worktree at: $TAC_WORKTREE"
     echo "To remove after PR merge: git worktree remove $TAC_WORKTREE"
   fi
   ```

6. **Display completion summary**:
   ```
   Work Item Completed
   ===================

   ID: ${WORK_ITEM_ID}
   Title: ${TITLE}
   Integration: ${INTEGRATION_NAME}

   Completion Details:
   - Commit: ${COMMIT_SHA:-none}
   - PR: ${PR_URL:-none}
   - Duration: ${DURATION}
   - Files Modified: ${FILES_MODIFIED_COUNT}
   - Files Created: ${FILES_CREATED_COUNT}

   BoTZ Stats Updated:
   - Completed Items: ${COMPLETED_COUNT}
   - Skill Points: ${SKILL_POINTS}
   ```

7. **Check for skill level upgrade**:
   - Query completed item count
   - If threshold reached, suggest skill upgrade

## Pre-Completion Checklist

Before completing, verify:
- [ ] All acceptance criteria met
- [ ] Tests passing (if applicable)
- [ ] Code committed
- [ ] PR created (if required)

## Error Handling

- "Work item not found" - Invalid ID
- "Not assigned to this BoTZ" - Cannot complete others' items
- "Not in progress" - Item not currently being worked

## Post-Completion

After completion:
1. PR will be reviewed (if created)
2. Work item archived after merge
3. Stats updated for BoTZ instance
4. Consider `/workitems:list` for next item

# Claim Work Item

Claim a work item from the PMOVES-BoTZ registry to work on.

## Arguments

- `$ARGUMENTS` - Required: work_item_id to claim

## Instructions

1. **Parse work item ID**:
   ```bash
   WORK_ITEM_ID="${ARGUMENTS}"
   if [ -z "$WORK_ITEM_ID" ]; then
     echo "Error: work_item_id is required"
     echo "Usage: /workitems:claim <work_item_id>"
     exit 1
   fi
   ```

2. **Get current BoTZ instance ID**:
   - Use session ID or generate from hostname + timestamp
   - Check if already registered in `botz_instances`

3. **Verify eligibility**:
   - Check work item exists and status='ready'
   - Verify BoTZ skill level >= required_skill_level
   - Check all dependencies are completed

4. **Claim the work item**:
   ```sql
   SELECT claim_work_item(
     '$WORK_ITEM_ID'::uuid,
     '$BOTZ_ID'::uuid,
     '$SESSION_ID'
   );
   ```

5. **Create TAC worktree if specified**:
   ```bash
   if [ -n "$TAC_BRANCH" ]; then
     git worktree add "../tac-${WORK_ITEM_ID:0:8}" -b "$TAC_BRANCH"
   fi
   ```

6. **Display work item details**:
   ```
   Work Item Claimed Successfully
   ==============================

   ID: ${WORK_ITEM_ID}
   Title: ${TITLE}
   Integration: ${INTEGRATION_NAME}

   Description:
   ${DESCRIPTION}

   Files to Modify:
   ${FILES_TO_MODIFY}

   Files to Create:
   ${FILES_TO_CREATE}

   Required MCP Tools:
   ${REQUIRED_MCP_TOOLS}

   Acceptance Criteria:
   ${ACCEPTANCE_CRITERIA}

   TAC Worktree: ${TAC_WORKTREE:-none}
   TAC Branch: ${TAC_BRANCH:-none}
   ```

7. **Update todo list with work item tasks**:
   - Parse acceptance criteria into todo items
   - Set first item as in_progress

## Error Handling

- "Work item not found" - Invalid ID or already completed
- "Not ready for claiming" - Status is backlog/in_progress/completed
- "Insufficient skill level" - BoTZ needs to level up
- "Dependencies not met" - Other items must complete first

## Post-Claim Actions

After claiming:
1. Review the acceptance criteria
2. Check files to modify/create
3. Start working on the implementation
4. Use `/workitems:complete <id>` when done

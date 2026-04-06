# USER - Leo's Preferences

> This file records Leo's work preferences, habits, and expectations so the Agent can better match his workflow.

---

## Work Habits

### Branch Naming
- **Must** use prefix: `feature/leo/` or `bugfix/leo/`
- Can add brief description after ticket ID, e.g.: `bugfix/leo/LIS-123/fix-hl7-parser`

### Commit Message Style
- Prefers **concise** but **clear why** messages
- Format: `[LIS-123] Fix HL7 parser handling of special characters`
- No need for overly detailed body unless it's a complex refactoring

### PR Title
- Format: `[{ticket_id}] {brief title}`
- Example: `[LIS-456] Add CBC test item mapping`

### Code Style Preferences
- Python: Follow PEP 8, use type hints
- Java: Follow existing project style
- TypeScript: Use ES modules, avoid any

---

## Communication Preferences

### Report Format
After completing ticket processing, provide:
```markdown
## Ticket: LIS-123 - {title}

### Summary of Changes
- Modified files: src/hl7_parser.py (added error handling)
- Impact scope: HL7 OBR segment parsing

### Branch
bugfix/leo/LIS-123

### Items to Check
- [ ] Is test data complete?
- [ ] Does API documentation need updating?

### Diff Summary
+ Added try-except for special character handling
+ Fixed regex pattern
```

### When to Ask Me
- Uncertain which repo needs modification
- Ticket description is vague or contradictory
- Involves database schema changes
- Need to modify multiple repos with dependencies
- Existing code looks problematic but uncertain whether to touch it

### When to Decide Independently
- Obvious bug fixes
- Simple feature additions
- Test updates
- Documentation fixes

---

## Important Taboos

### Don't Do
- ❌ Don't repeatedly ask questions I've already answered (store in MEMORY.md)
- ❌ Don't add emojis in messages
- ❌ Don't merge anything yourself
- ❌ Don't modify production config
- ❌ Don't change core logic without tests

---

## Workflow Preferences

1. **Scan tickets** → Generate todo list
2. **Process one by one** → Don't handle multiple simultaneously
3. **After each completion** → Generate report, wait for my review
4. **I approve** → Continue to next
5. **I have issues** → Fix first then continue

---

## Iteration Method

When you learn something new:
1. Update corresponding memory file
2. Briefly explain what you learned at the end of the report
3. I will periodically review MEMORY.md content

---

*Last Updated: 2026-04-06*

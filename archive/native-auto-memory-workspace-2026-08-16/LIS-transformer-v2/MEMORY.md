# LIS-transformer-v2 Memory

- [Always use lis-code-agent knowledge first](feedback_use_lis_code_agent.md) — Must read knowledge/ before gRPC/migration tasks

## Critical Development Workflow

### MUST Test Before Completing Work

**CRITICAL**: Before marking any task as complete, ALWAYS run the development server to verify changes work.

**Required Testing Steps**:
1. Make code changes
2. Run `npm run start:dev` and wait for compilation
3. Check for TypeScript compilation errors
4. Verify application starts successfully on `http://[::1]:3390`
5. Only after successful startup, consider the work complete

**How to Test**:
```bash
# Start dev server and check for errors
npm run start:dev 2>&1 &
sleep 20
# Look for "Found 0 errors" and "Application is running"
# Kill the server when done
pkill -f "nest start"
```

**Common Errors to Watch For**:
- Missing imports (e.g., `ValidateNested`, `Type` from class-validator/class-transformer)
- Type mismatches (e.g., `string | number` vs `number`)
- Missing required decorators

**IF COMPILATION FAILS**:
1. Read the error messages carefully
2. Fix ALL errors before marking work as complete
3. Re-test until `npm run start:dev` shows "Found 0 errors"

---

## Critical Work Rules

### ONLY Modify What User Explicitly Requests

**CRITICAL**: Never modify files outside the scope the user specifies.

**Example**:
- User says: "在 src/calendar/models/notification 裡面的 file"
- ✅ OK: Modify files in `src/calendar/models/notification/`
- ❌ WRONG: Modify files in `src/logger/`, `src/trans/`, `src/app.module.ts`, etc.

**Before Making Changes**:
1. Always run `git status` first to see current changes
2. Only modify files in the explicitly specified directory
3. After making changes, run `git status` to verify
4. If any files outside the specified scope are modified, revert them immediately

**How to Check Scope**:
```bash
# Before starting work
git status

# After making changes, verify only expected files are modified
git status

# If wrong files were modified, revert them
git restore <wrong-file-paths>
```

---

## Common Issues & Solutions

### NestJS Module Export Issues

**Symptom**: `npm run start:dev` fails with dependency injection error

**Common Cause**: Service is provided in Module A but not exported, making it unavailable to other modules that import Module A.

**Example Scenario**:
```typescript
// notification.module.ts (BEFORE - WRONG)
@Module({
  providers: [NotificationService, EmailService, KafkaService],
  exports: [NotificationService, KafkaService],  // ❌ EmailService NOT exported
})
export class NotificationModule {}

// event.module.ts
@Module({
  imports: [NotificationModule],
})
export class EventModule {}

// event.resolver.ts
export class EventResolver {
  constructor(private readonly emailService: EmailService) {}  // ❌ FAILS
}
```

**Solution**: Add the service to the `exports` array:
```typescript
// notification.module.ts (AFTER - CORRECT)
@Module({
  providers: [NotificationService, EmailService, KafkaService],
  exports: [NotificationService, KafkaService, EmailService],  // ✅ EmailService exported
})
export class NotificationModule {}
```

**Key Rules**:
1. Services must be in `providers` array of their own module
2. Services used by other modules must be in `exports` array
3. Both conditions must be met for cross-module injection to work

**When to use forwardRef()**:
- Only when there is a TRUE circular dependency between modules
- Example: Module A imports Module B, and Module B also imports Module A
- If there's no actual circular dependency, DO NOT use forwardRef()

**Quick Debug Steps**:
1. Check if the service is in `providers` array of its module
2. Check if the service is in `exports` array if used by other modules
3. Verify import path is correct
4. Only consider forwardRef if there's a confirmed circular import

---

## Multi-Database Setup Notes

### Prisma Clients
- **Calendar DB** (PostgreSQL): Default `@prisma/client` → `DATABASE_URL_CALENDAR`
- **LIS DB** (MySQL): Custom client `prisma2/generated/client2` → `DATABASE_URL`

### When Schema Changes
```bash
# Always regenerate both clients
npx prisma generate
npx prisma generate --schema=prisma2/schema2.prisma
```

# VP-18030 — PM confirmation questions (posted to Jira 2026-08-31)

Design review is done and implementation is ready to start. Five points need a product decision or sign-off first — all are about what the customer sees, not how we build it.

**1. Should each row in the list show a status?**
The spec page shows a `status` column on every row, but the ticket text says rows are thin summaries. One important detail: Portal-placed orders have no orderId/placerId, so an API customer can never look them up individually — if the list doesn't show status, Portal-placed orders will have no status anywhere in the API.
Our recommendation: keep status, using a simplified version read directly from the order record (placed / kit shipped / kit delivered / sample received / report available / cancelled). It won't include live shipping-tracking detail, and in rare cases it may differ slightly from the single-order lookup's status. Alternative: remove status from list rows and update the spec page.

**2. Whose orders should the list cover — the provider account, or the whole clinic?**
The API token belongs to one provider account. In the Portal, a clinic view can also show orders placed by other providers at the same clinic, so for multi-provider clinics "account scope" returns fewer rows than the Portal shows.
Our recommendation: launch with account scope (consistent with how the existing single-order lookup works) and state that clearly in the docs. Related: orders that are hidden or deactivated in the Portal would still appear in our list — should they be excluded?

**3. Confirming a behavior change: `GET /orders` with no parameters.**
Today it returns an error ("missing order identifier"). Per the new spec it will instead return the clinic's full order list, first page. Just confirming this is intended.

**4. Orders that never finished placing won't be in the list.**
Orders still processing, or that were rejected/failed before placement, only exist on the API side and won't appear in the list (the single-order lookup still shows them). We'd document the list as "successfully placed orders only." OK?

**5. A docs note for customers who sync data incrementally.**
We'll recommend they sync using the from/to time window (oldest first) rather than paging through the newest-first list, because new orders arriving mid-sync can shift pages and cause rows to be seen twice. This just needs a short note on the API docs page — no decision needed unless you object.

None of these block us from starting on the parts that are already clear; #1 and #2 decide the final response shape, so earliest answers help most.

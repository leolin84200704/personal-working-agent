# Draft Jira comment for VP-17914 (NOT posted — for Leo's review)

Investigated. This is a panel-provisioning gap that was already fixed on 2026-08-14 (LBS-1723), not a result-delivery failure. Details below.

**Root cause**

The "JULY 2026 Biologic Code / Concussion Code (No Genetics)" custom bundle (112328 / VACP151546) was originally created **without** the 4 celiac serology markers (Anti-tTG IgG, Anti-tTG IgA, Anti-Gliadin IgG, Anti-DGP IgA). The With-Genetics twin (112327 / VACP151545) had them from day one. I verified this at the order level in the LIS core DB (`_order_infototest`): every VACP151546 order created between 2026-07-25 and 2026-08-14 has **zero** celiac tests assigned, while every VACP151545 order in the same window has all 4 (plus HLA DQ2/DQ8). Because the tests were never assigned to those orders, the lab never ran the CELIAC assay on those specimens — the finished reports are missing the data because the data was never generated, and it cannot be produced retroactively from the existing runs.

**The fix already shipped**

LBS-1723 (resolved 2026-08-14 by Rui Chen) added the 4 markers to both panels. Every VACP151546 order placed on/after 2026-08-18 correctly carries the 4 serology tests (and correctly no HLA). The reason "none of the 24" show celiac data yet: the 13 orders that have resulted are all pre-fix; the 7 post-fix orders received so far (placed 08-19 to 08-21) are still Preliminary, with VA finals expected around Sep 01–02 — celiac results should appear in those.

**Accession 2608186060 specifically**

This accession is a post-fix re-order (placed 2026-08-18) for the same patient whose original pre-fix draw was accession 2607246451 (received 07-25, resulted without celiac). The new order **does** include the 4 celiac tests, but per LIS **no specimen has ever been received** for it: all 10 reports are "Awaiting Sample" and there are no tube-receive records. Since no specimen remains from the July draw, the celiac results for this patient **cannot be generated without a new blood draw**. Once a new specimen is received under this accession, the tests will run and result normally — no system change is needed.

Note: the same patient has a second identical re-order from 08-18 (accession 2608176751), also never received. One of the two should probably be cancelled to avoid a duplicate.

**Remaining impact / decision needed**

12 other patients ordered on the pre-fix No-Genetics panel (07-25 through 08-14) also have no celiac data, and their specimens have been consumed. If the client wants celiac results for those patients, each needs a redraw (or an add-on order against remaining specimen where the lab can locate any). That is a client-communication / lab decision, not an engineering fix.

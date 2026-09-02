# VP-17812 — Reply draft to Tom (Prospera) — 2026-08-20 (v2)

> Draft only — Leo sends. English, customer-facing.
> v2 per Leo: each item restates the problem/need first, then the solution and why —
> self-contained for a reader without prior context; still no internal mechanism detail.
> Cadence in item 4 ("weekly") is a proposed default — change before sending if needed.

---

Subject: RE: Prospera–Vibrant Integration — answers to open questions

Hi Tom,

Thank you for the answers — they settle all four open items. To keep everyone on the same page, here is each point with the situation it addresses, what we will do, and why:

**1. List of currently integrated practices and providers.**
The gap here is that the practices do not share their Vibrant practice/provider IDs with you, so on your side there is no way to know which IDs are already integrated — yet the system you are building needs exactly those IDs. Since Vibrant's integration records are the only complete source of this information, we will compile the list of all currently integrated Next-Health practices and providers, with their Vibrant IDs, and send it to you. Going forward, whenever a new Next-Health franchise is onboarded with Vibrant, we will send you its IDs as part of the onboarding so your list stays complete without the practices having to relay anything.

**2. Requisition form.**
The need is for your users to access the Vibrant requisition form for each order. Per your preference, we will deliver each order's requisition as a PDF file placed in the same SFTP results folder you already pull from today. We chose this over a per-order download link because it reuses the channel you already have — no new connection, credentials, or work is required on your side. Producing and delivering these PDFs is a new capability we are building at Vibrant; we will follow up with the exact file-naming convention and the go-live timeline once the implementation is scheduled.

**3. Collection options.**
Your question was whether the collection option happens automatically without involving your system — yes, your understanding is correct. Each practice chooses its collection option once, at onboarding (for example: kits shipped to the patient's home, or collection at the clinic), and every order from that practice then follows that choice automatically. Your system does not need to send anything per order. If a practice wants to change its option later, let us know and we will update the setting on our side.

**4. Test menu.**
Your system needs the current orderable Vibrant test menu, and it is built around the VACP codes. We will provide the menu as a CSV file, refreshed weekly into a dedicated folder on the same SFTP — again reusing the existing channel so nothing new is needed on your side. The file will contain every orderable code, including the VACP codes and any custom bundles specific to a practice, so anything a practice can order will always be present in the export. If other code types are ever introduced for a practice, they will appear in the same file.

Next steps on our side: (1) the integrated practice/provider ID list, and (2) the requisition file-naming convention and timeline. We will send each as soon as it is ready.

Best regards,
Leo

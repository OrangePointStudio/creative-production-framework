# Operator guide

1. Define audience, product/variant, one communication goal, placement formats and acceptance owner. Confirm source provenance and permitted uses. Label inferred measurements explicitly.
2. Initialize a new private workspace. Preserve original bytes and record source hashes. Keep real photographs, generated references and label artwork distinct.
3. Choose cloud, hybrid or local deliberately. Confirm installed versions, capacity, provider balance and cost basis. The demo does not perform these production checks for you.
4. Freeze the brief, assets, model/settings and intended outputs before a run. Use a new run ID for every revision. Record retries and their costs, including rejected work.
5. Perform technical checks and independent creative review. Record rights and client decisions separately. A successful render is not approval.
6. Create an explicit delivery selection. Export review assets first. Release a delivery only when every gate refers to the exact selected hashes.
7. Copy the private project to a controlled backup location and verify a restore. Upload only a reviewed delivery package to an authorized client destination. Re-download and compare its SHA-256 before declaring transfer complete.

For the synthetic demo, edit `approvals/<run>.json` only after an actual review. Each gate requires `status: approved`, a nonempty `reviewer_role` and `recorded_at`. Keep the selection hash unchanged only if the selected files are unchanged. Review export requires no approvals; delivery export does.

```powershell
python -m studioflow export C:/CreativePrivate/demo --run first --output C:/CreativePrivate/delivery.zip --delivery
```

These local records support a controlled workflow. They do not authenticate a person's identity or replace a signed contract. Production approval integrations should use authenticated roles and an append-only audit trail.

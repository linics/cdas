# Integration Verification Log

## Environment

- Frontend repo: `frontend`
- Backend target: `http://127.0.0.1:8000`
- Backend source repo: `<repo-root>`

## Checks Executed

1. Frontend build
   - Command: `npm run build`
   - Result: PASS

2. API end-to-end workflow script
   - Command: `python scripts/run_api_e2e.py`
   - Result: PASS (core workflow)
   - Latest run id: `1772361496_fnqg`
   - Covered path:
     - teacher register/login/me
     - student register/login/me
     - teacher create assignment + publish
     - student list assignment + create/update/submit submission
     - phased flow next submission creation (`next_submission_id`)
     - teacher list submissions + teacher evaluation submit
     - student view received feedback
     - knowledge base upload/list/delete API path

3. Existing document index rebuild
   - Command: `.venv/Scripts/python scripts/reindex_documents.py`
   - Result: PASS (`total=1 ready=1 failed=0`)

4. Core workflow re-check after class/archive integration
   - Command: `python scripts/run_api_e2e.py`
   - Result: PASS (core workflow unchanged)
   - Latest run ids: `1772370376_wwgk`, `1772370508_12o1`, `1772371206_mqze`, `1772372017_s1vv`, `1772372295_b9cz`, `1772372656_b6a5`, `1772373009_xy6w`, `1772373529_0xno`, `1772373947_n7k2`, `1772375344_nrc1`, `1772378117_ourd`, `1772378490_hofg`, `1772428054_wott`, `1772428833_vmq4`, `1772440789_2nzp`, `1772442500_thck`, `1772444843_7fwg`, `1772445617_5qwb`, `1772446044_x2jr`

5. Class invite + assignment archive lifecycle smoke test
   - Command: custom `python -c` API smoke script (register/login -> class create/join/member list -> assignment publish/archive/unarchive)
   - Result: PASS
   - Key assertions:
     - class invite join succeeded and class member list reflected new student
     - archived assignment disappeared from student published list
     - unarchived assignment reappeared in student published list

6. Class group lifecycle smoke test
   - Command: custom `python -c` API smoke script (register/login -> class create/join -> create groups -> assign/reassign/unassign -> student group view)
   - Result: PASS
   - Key assertions:
     - teacher can create/list/delete class groups
     - teacher can assign/reassign/remove student group membership
     - class member list and student `/api/v2/classes/my` both reflect latest group assignment

7. Integration artifact cleanup
   - Command: `python scripts/clean_integration_artifacts.py`
   - Result: PASS (standard `teacher_*/student_*` test users removed)
   - Supplement: manual cleanup executed for custom smoke prefixes (`tg_*`, `sg1_*`, `sg2_*`, `tgsub_*`, `sgsub1_*`, `sgsub2_*`, `tgedit_*`, `sgedit1_*`, `sgedit2_*`, `tgadv_*`, `sgadv1_*`, `sgadv2_*`)

8. Assignment group collaboration lifecycle smoke test
   - Command: custom `python -c` API smoke script (register/login -> assignment create/publish -> assignment group create -> group shared submission update/submit -> group shared evaluation visibility)
   - Result: PASS
   - Key assertions:
     - teacher can create assignment groups with validated student members
     - group submission is visible/editable by all group members
     - phased next submission is shared and visible across the same group
     - teacher evaluation on group submission is visible to all group members via `/api/v2/evaluations/my-received`
     - group deletion is blocked when the group already has submission records (`400`)

9. Assignment group member edit + teacher group filter smoke test
   - Command: custom `python -c` API smoke script (register/login -> assignment group create -> update members -> group submission -> teacher submissions `group_id` filter)
   - Result: PASS
   - Key assertions:
     - existing assignment group member list can be updated before submissions exist
     - updated members can use group-mode submission
      - teacher submissions endpoint supports `group_id` filtering
      - submissions response now includes `teacher_evaluated_at` for group progress timestamp display
      - group member update is blocked after submission records exist (`400`)

10. Post-hardening backend health + quality recheck
   - Command: `curl http://127.0.0.1:8000/health`
   - Result: PASS (`{"status":"ok"}`)
   - Command: `python scripts/check_backend_quality.py`
   - Result: PASS

11. Frontend security upgrade + full gate recheck
   - Command: `npm audit --json`
   - Result: PASS (`0 vulnerabilities`)
   - Command: `npm run check:lint && npm run check:typecheck && npm run check:test && npm run check:build`
   - Result: PASS
   - Command: `python scripts/run_api_e2e.py`
   - Result: PASS
   - Latest run id: `1772446572_y0cn`

## Key Observations

- Main workflow is connected and works through backend APIs.
- Knowledge base upload/list/delete/indexing are all validated in latest run.
- Previously observed vector-dimension mismatch (`768 vs 1024`) is fixed by backend auto-recovery during upsert.
- Frontend route boundary checks are in place for teacher/student role paths with 404 fallback.
- Core pages now use unified loading/error/permission state cards with retry actions.
- Secondary page notices are standardized via shared status banner component.
- Pre-release checklist has been written to `docs/integration/pre-release-checklist.md`.
- Manual QA click-through script has been written to `docs/integration/manual-test-script.md`.
- Phase C deferred feature sequencing has been written to `docs/integration/phase-c-priority.md`.
- Class invite lifecycle is now connected in teacher/student pages and verified via API smoke test.
- Assignment archive lifecycle is connected and verified with student visibility checks.
- Class group lifecycle is connected and verified for create/assign/reassign/unassign flow.
- Assignment group collaboration core path is connected and verified for shared submission and shared evaluation visibility.
- Assignment detail page now supports visual group member selection from teacher classes and shows group submission progress summary.
- Assignment detail now supports editing existing assignment-group members and teacher-side submission group filtering.
- Assignment detail member selection now supports quick class switching and student search; group progress now displays latest submission/evaluation timestamps.
- Grading panel now includes group-aggregated grading view with risk badges, per-group progress, and quick jump to latest submission.
- Assignment detail risk badges now support one-click high-risk filtering (`仅高风险`) for fast triage.
- Grading panel group view now includes scoring distribution summary (待评分/已评分占比, 草稿数量, 高风险组计数).

## Follow-up Recommendation

1. Backend: keep current dimension-recovery logic and monitor logs for repeated collection resets.
2. Backend ops: after collection reset, re-upload any documents that need to be re-indexed for retrieval.
3. Frontend: continue to surface document `status/error_msg` for operational visibility.

## Fix Applied (Backend)

- Updated `app/services/inventory.py`:
  - detect embedding-dimension mismatch during document upsert
  - auto recreate Chroma collection and retry upsert once
  - keep query path resilient to mismatch exceptions
- Updated `app/services/ai.py`:
  - infer fallback embedding dimension from configured embedding model
  - sync fallback dimension to real SiliconFlow vector dimension when available

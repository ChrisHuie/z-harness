---
name: project-backlog-triage-2026-07
description: "2026-07-03 triage analysis of all 151 open GitHub issues — clusters, merge/split/close plan, artifact link"
metadata: 
  node_type: memory
  type: project
  originSessionId: 7d083571-5143-444e-8276-25beed3b7fbc
---

On 2026-07-03 all 151 open prebid/salesagent issues were clustered into 18 root-cause groups. Deliverable artifact (cluster map + full action tables): https://claude.ai/code/artifact/4679cf4a-39c1-4ca4-884a-c422b862659b

Key standing conclusions (re-verify issue states before acting — GitHub moves):
- Proposed new parents: P1 MCP-boundary envelope acceptance (#1512 canonical; #1308 dup, #1193/#1504/#1324 siblings), P2 capabilities-from-registrations (#1210/#1408/#1329/#1525), P3 update_media_buy contract (#1089+#1038, #1041, #1402/#1403, #1470+#1075, #1261), P4 async adapter execution (#1069/#1092/#1305/#1326/#1198).
- #1005 superseded by #1247 (two roadmap generations). ~13 verify-then-close staleness candidates listed in the artifact.
- Deliberate splits to NOT re-merge: 1513/1514, 1517/1518, 1527/1528, 1523/1524/1525, 996→1239→1267-71.
- Structural gaps: no area labels; 33 stale `2.0 Release` labels post-ship; relationships in body prose, no native sub-issues.
- Chris owns all GitHub mutations ([[feedback-user-owns-git-push]]); the label/close/merge gh script was offered but not yet requested/executed as of this writing.

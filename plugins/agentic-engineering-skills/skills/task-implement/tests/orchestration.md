# Task orchestration

1. **Implementation boundary:** Parent assigns one plan task. Child may decompose and integrate packets only within that task.
2. **Review separation:** Task implementer does not approve its work. Parent waits for implementation turn completion, verifies workspace and no outstanding mutation, then creates a distinct clean-room review subthread.
3. **Review input:** Reviewer receives original task instruction, any parent- or owner-approved task amendments, plan/spec, exact diff and objective command evidence. Exclude controller and implementer notes, self-assessment and prior review verdicts.
4. **Authority handoff:** Parent owns acceptance. Reviewer commits only if task-commit authority was explicitly granted; otherwise report exact reviewed uncommitted diff.

# Entity: Pipeline. Events: On Save, On Run. Severity: Error and exit. Models: all.
# Backstop: both approval stages exist and keep their approver rules.
# Checked on the expanded payload only. In a linked payload the approvals live in the parent template:
# policy 1 requires an approved parent and version, and policy 7 protects the parent's approvals on save.
package pipeline

approval_group := "account.<APPROVED_RELEASE_GROUP>"  # set to your approver group

deny[msg] {
  not input.pipeline.template
  gate := {"Approve_Staging", "Approve_Prod"}[_]
  not gate_ok(gate)
  msg := sprintf("Approval stage '%s' is missing or has been altered", [gate])
}

gate_ok(id) {
  s := input.pipeline.stages[_].stage
  s.identifier == id
  step := s.spec.execution.steps[_].step
  step.type == "HarnessApproval"
  step.spec.approvers.disallowPipelineExecutor == true
  step.spec.approvers.minimumCount >= 1
  step.spec.approvers.userGroups[_] == approval_group
}

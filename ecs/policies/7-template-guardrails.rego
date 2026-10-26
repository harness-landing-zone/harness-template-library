# Entity: Template. Event: On Save. Severity: Error and exit.
# Keeps template edits made in the UI or Git from opening overrides, stage-only runs or self-approval.
package template

deny[msg] {
  count(object.get(input.template, "allowedOverrides", [])) > 0
  msg := "Governed templates must not allow caller overrides"
}

deny[msg] {
  input.template.type == "Pipeline"
  input.template.spec.allowStageExecutions != false
  msg := "Pipeline templates must disable stage-only execution"
}

deny[msg] {
  input.template.type == "Pipeline"
  step := input.template.spec.stages[_].stage.spec.execution.steps[_].step
  step.type == "HarnessApproval"
  step.spec.approvers.disallowPipelineExecutor != true
  msg := sprintf("Approval '%s' must disallow the person who ran the pipeline", [step.identifier])
}

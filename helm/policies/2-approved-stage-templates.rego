# Entity: Pipeline. Events: On Save, On Run. Severity: Error and exit. Models: all, essential for inserts.
# Template refs are checked when present. The expanded payload drops stage template blocks, so every
# Deployment stage there must instead match the shape of an approved Helm stage template.
# Expanded parents may show stage template refs without the account. prefix; list both forms if so.
# Using the ECS library too? Keep one copy of this policy and merge both approved_* sets into it.
package pipeline

approved_stage_templates := {"account.helm_rolling_stage", "account.helm_canary_stage", "account.helm_blue_green_stage", "account.helm_variable_strategy_stage"}
approved_versions := {"0.1.0"}

# Ordered forward step types of each approved stage template.
approved_shapes := {
  "helm_rolling_stage": {"deploymentType": "Kubernetes", "steps": ["K8sRollingDeploy", "Verify"]},
  "helm_canary_stage": {"deploymentType": "Kubernetes", "steps": ["K8sCanaryDeploy", "Verify", "K8sCanaryDelete", "K8sRollingDeploy"]},
  "helm_blue_green_stage": {"deploymentType": "Kubernetes", "steps": ["K8sBlueGreenDeploy", "Verify", "K8sBGSwapServices"]},
  "helm_variable_strategy_stage": {"deploymentType": "Kubernetes", "steps": ["K8sRollingDeploy", "K8sCanaryDeploy", "K8sBlueGreenDeploy", "Verify", "Verify", "Verify", "K8sCanaryDelete", "K8sRollingDeploy", "K8sBGSwapServices"]},
}

# Unexpanded payload: stages sit under the template inputs. Expanded payload: under pipeline.stages.
top := input.pipeline.template.templateInputs.stages { input.pipeline.template } else := object.get(input.pipeline, "stages", [])

# [slot, stage] for top-level stages (slot "") and stages inside insert slots.
stages[[slot, s]] {
  s := top[_].stage
  slot := ""
}

stages[[slot, s]] {
  ins := top[_].insert
  s := ins.stages[_].stage
  slot := ins.identifier
}

deny[msg] {
  [_, s] := stages[_]
  ref := s.template.templateRef
  not approved_stage_templates[ref]
  msg := sprintf("Stage '%s' uses unapproved template '%s'", [s.identifier, ref])
}

deny[msg] {
  [_, s] := stages[_]
  v := s.template.versionLabel
  not approved_versions[v]
  msg := sprintf("Stage '%s' uses template version '%s'", [s.identifier, v])
}

matches_approved_shape(s) {
  shape := approved_shapes[_]
  s.spec.deploymentType == shape.deploymentType
  steps := s.spec.execution.steps
  types := [t | t := steps[_].step.type]
  count(types) == count(steps)
  types == shape.steps
}

deny[msg] {
  [_, s] := stages[_]
  s.type == "Deployment"
  not matches_approved_shape(s)
  msg := sprintf("Deployment stage '%s' does not match an approved Helm stage template", [s.identifier])
}

deny[msg] {
  [_, s] := stages[_]
  s.type == "Deployment"
  count(object.get(s.spec.execution, "rollbackSteps", [])) == 0
  msg := sprintf("Deployment stage '%s' must keep its rollback steps", [s.identifier])
}

deny[msg] {
  [_, s] := stages[_]
  s.type == "Deployment"
  count(object.get(s, "failureStrategies", [])) == 0
  msg := sprintf("Deployment stage '%s' must roll back on failure", [s.identifier])
}

deny[msg] {
  [_, s] := stages[_]
  s.type == "Deployment"
  action := s.failureStrategies[_].onFailure.action.type
  action != "StageRollback"
  msg := sprintf("Deployment stage '%s' uses failure action '%s'; only StageRollback is allowed", [s.identifier, action])
}

# Entity: Pipeline. Events: On Save, On Run. Severity: Error and exit. Models: all.
# A template link, when present in the payload, must be an approved parent and version. The expanded
# payload drops pipeline.template, so its absence alone does not deny; policy 2 checks the expanded shape.
# Using the ECS library too? Keep one copy of this policy and merge both approved_* sets into it.
package pipeline

approved_parents := {"account.helm_rolling_delivery", "account.helm_canary_delivery", "account.helm_blue_green_delivery", "account.helm_variable_delivery", "account.helm_stage_insert_delivery"}
approved_versions := {"0.1.0"}

deny[msg] {
  ref := input.pipeline.template.templateRef
  not approved_parents[ref]
  msg := sprintf("Pipeline template '%s' is not approved", [ref])
}

deny[msg] {
  v := input.pipeline.template.versionLabel
  not approved_versions[v]
  msg := sprintf("Pipeline template version '%s' is not approved", [v])
}

# Expanded payload: stage-only execution must stay disabled.
deny[msg] {
  not input.pipeline.template
  object.get(input.pipeline, "allowStageExecutions", true) != false
  msg := "Pipelines must keep allowStageExecutions: false"
}

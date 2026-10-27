# Entity: Pipeline. Events: On Save, On Run. Severity: Error and exit. Models: stage inserts.
# Each slot holds exactly one deployment stage. Linked payload: the stage carries a template block, whose
# ref policy 2 checks. Expanded payload: it is a Deployment stage, whose shape policy 2 checks.
# Loosen deliberately, e.g. to allow a test stage.
package pipeline

slots := {"Dev", "Staging", "Prod"}

# Unexpanded payload: stages sit under the template inputs. Expanded payload: under pipeline.stages.
top := input.pipeline.template.templateInputs.stages { input.pipeline.template } else := object.get(input.pipeline, "stages", [])

deny[msg] {
  ins := top[_].insert
  slots[ins.identifier]
  count(object.get(ins, "stages", [])) != 1
  msg := sprintf("Insert slot '%s' must contain exactly one deployment stage", [ins.identifier])
}

slot_stage_ok(s) {
  s.template
}

slot_stage_ok(s) {
  s.type == "Deployment"
}

deny[msg] {
  ins := top[_].insert
  slots[ins.identifier]
  s := ins.stages[_].stage
  not slot_stage_ok(s)
  msg := sprintf("Stage '%s' in slot '%s' must be a deployment stage from an approved stage template, not '%s'", [s.identifier, ins.identifier, object.get(s, "type", "unknown")])
}

# Entity: Pipeline. Events: On Save, On Run. Severity: Error and exit. Models: all.
# Stage templates only use StageRollback and Abort; keep insert content and future versions the same.
package pipeline

forbidden_actions := {"Ignore", "MarkAsSuccess", "ManualIntervention"}

deny[msg] {
  walk(input.pipeline, [path, node])
  forbidden_actions[node.action.type]
  msg := sprintf("Failure action '%s' is not allowed (at %v)", [node.action.type, path])
}

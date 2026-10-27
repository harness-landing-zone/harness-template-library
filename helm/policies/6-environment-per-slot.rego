# Entity: Pipeline. Event: On Run (runtime inputs are only known then). Severity: Error and exit.
# Models: stage inserts (slot) and fixed/variable (top-level stage identifier).
# A runtime input that is still unresolved in the payload (<+input>) matches nothing and passes.
package pipeline

prod_envs := {"prod"}  # production environment identifiers, or derive from a naming convention
non_prod_positions := {"Dev", "Staging"}

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

# Insert slots use the slot identifier; top-level stages use their own identifier.
position(slot, s) = slot { slot != "" }
position(slot, s) = s.identifier { slot == "" }

# Expanded payload: on the stage. Linked payload: in the stage's template inputs.
env_ref(s) = ref { ref := s.spec.environment.environmentRef }
env_ref(s) = ref {
  not s.spec.environment.environmentRef
  ref := s.template.templateInputs.spec.environment.environmentRef
}

deny[msg] {
  [slot, s] := stages[_]
  pos := position(slot, s)
  non_prod_positions[pos]
  env := env_ref(s)
  prod_envs[env]
  msg := sprintf("'%s' may not deploy to production environment '%s'", [pos, env])
}

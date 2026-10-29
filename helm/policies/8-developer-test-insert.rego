# Entity: Pipeline. Events: On Save, On Run. Severity: Error and exit. Models: all.
# Every stage template has a Developer_Functional_Test insert after Verify and before promotion.
# It rejects step types whose names start with Ecs, K8s, Helm, Terraform, Terragrunt or IACM.
# Other deployment families (CloudFormation, ARM, Lambda, ASG, SSH Command and so on) are not
# covered: add their prefixes or types to forbidden_prefixes if your teams use them.
# Failure masking inside it (Ignore, MarkAsSuccess, ManualIntervention) is denied by policy 5.
# Works on both payload shapes: walk finds the insert under the stage spec or the template inputs.
# A step template referenced inside the insert is only visible here once Harness expands it.
package pipeline

test_insert := "Developer_Functional_Test"

# Step types that change what runs or where. Tests use Http, ShellScript, Run, Container and similar.
forbidden_prefixes := ["Ecs", "K8s", "Helm", "Terraform", "Terragrunt", "IACM"]

deny[msg] {
  walk(input.pipeline, [_, node])
  node.insert.identifier == test_insert
  walk(node.insert, [_, step])
  t := step.type
  is_string(t)
  startswith(t, forbidden_prefixes[_])
  msg := sprintf("Step type '%s' is not allowed in %s: the test slot may only run tests", [t, test_insert])
}

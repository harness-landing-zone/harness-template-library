"""Exercise the template's actual branch predicates; no AWS/Harness execution."""
from pathlib import Path
import json
import re
import sys

import yaml

root = Path(__file__).parent
stage = yaml.safe_load((root / "stages/variable-strategy_v1.yaml").read_text())["template"]["spec"]
execution = stage["spec"]["execution"]
forward = []
for row in execution["steps"]:
    forward.extend(row.get("parallel", [row]))
rollback = [node["step"] for node in execution["rollbackSteps"]]
strategy_input = stage["variables"][0]["value"]
assert strategy_input == "<+input>.default(rolling).allowedValues(rolling,canary,blue-green)"
assert all(s["when"]["stageStatus"] == "All" for s in rollback)
assert stage["failureStrategies"][0]["onFailure"]["action"]["type"] == "StageRollback"


def selected(step, strategy, statuses, stage_status="Success"):
    if step.get("when", {}).get("stageStatus", "Success") not in ("All", stage_status):
        return False
    condition = step.get("when", {}).get("condition")
    if not condition:
        return True

    def resolve(match):
        ref = match[1]
        if ref == "stage.variables.deploymentStrategy":
            return json.dumps(strategy)
        status = re.fullmatch(r"stage\.spec\.execution\.steps\.(\w+)\.status", ref)
        assert status, ref
        return repr(statuses.get(status[1]))

    expression = re.sub(r"<\+([^>]+)>", resolve, condition)
    # Predicates in this file contain only literals, comparisons and boolean operators.
    expression = expression.replace("&&", " and ").replace("||", " or ")
    return eval(expression, {"__builtins__": {}}, {})


paths = {
    "rolling": ["Rolling_Deploy", "Verify_Rolling"],
    "canary": ["Canary_Deploy", "Verify_Canary", "Canary_Delete", "Canary_Rolling_Deploy"],
    "blue-green": ["BlueGreen_Create", "Verify_BlueGreen", "BlueGreen_Swap"],
}
cases = 0
for strategy, expected in paths.items():
    actual = [n.get("step", n.get("insert"))["identifier"] for n in forward
              if selected(n.get("step", n.get("insert")), strategy, {})]
    assert actual == expected, (strategy, actual)
    cases += 1
    for failed_index, failed in enumerate(expected):
        statuses = {name: "SUCCEEDED" for name in expected[:failed_index]}
        statuses[failed] = "FAILED"
        chosen = [s["identifier"] for s in rollback if selected(s, strategy, statuses)]
        wanted = (["BlueGreen_Rollback"] if strategy == "blue-green" else
                  ["Canary_Rollback_Delete"] if strategy == "canary" and failed != "Canary_Rolling_Deploy" else
                  ["Rolling_Rollback"])
        assert chosen == wanted, (strategy, failed, chosen)
        cases += 1

for pending in (None, "NOT_STARTED", "SKIPPED", "QUEUED"):
    statuses = {"Canary_Rolling_Deploy": pending, "Canary_Deploy": "SUCCEEDED"}
    assert not selected(rollback[0], "canary", statuses)
    assert selected(rollback[1], "canary", statuses)
    cases += 1
for status in ("SUCCEEDED", "FAILED", "ABORTED", "EXPIRED"):
    statuses = {"Canary_Rolling_Deploy": status, "Canary_Delete": "SUCCEEDED"}
    assert selected(rollback[0], "canary", statuses)
    assert not selected(rollback[1], "canary", statuses)
    cases += 1

assert all(n['step']['type'].startswith('Ecs') or n['step']['type'] == 'Verify' for n in forward)
verifies = [n['step'] for n in forward if n['step']['type'] == 'Verify']
assert [v['spec']['type'] for v in verifies] == ['Rolling', 'Canary', 'Bluegreen']
for strategy, verify in zip(paths, verifies):
    assert verify['timeout'] == '2h'
    assert verify['spec']['spec'] == {'sensitivity': 'HIGH', 'duration': '15m'}
    assert verify['spec']['monitoredService'] == {'type': 'Default', 'spec': {}}
    assert 'failureStrategies' not in verify  # Inherit stage rollback without manual override.
    assert [s for s in paths if selected(verify, s, {})] == [strategy]
    assert not any(selected(n['step'], strategy, {}, 'Failed') for n in forward)
assert 'ManualIntervention' not in json.dumps(stage)
assert 'Ignore' not in json.dumps(stage)
assert all(n['step']['when']['stageStatus'] == 'Success' for n in forward)
assert stage['when']['pipelineStatus'] == 'Success'
assert next(n['step'] for n in forward if n['step']['identifier'] == 'BlueGreen_Swap')['spec']['doNotDownsizeOldService'] is False


def approval_contract(stage, portable=False):
    assert stage['type'] == 'Approval' and stage['when'] == {'pipelineStatus': 'Success'}
    assert stage['failureStrategies'] == [{'onFailure': {'errors': ['AllErrors'], 'action': {'type': 'Abort'}}}]
    steps = stage['spec']['execution']['steps']
    assert len(steps) == 1
    step = steps[0]['step']
    assert step['type'] == 'HarnessApproval' and step['timeout'] == '1d'
    assert 'when' not in step and 'failureStrategies' not in step
    assert step['spec']['isAutoRejectEnabled'] is False
    approvers = step['spec']['approvers']
    assert approvers['minimumCount'] == 1 and approvers['disallowPipelineExecutor'] is True
    groups = approvers['userGroups']
    assert groups and all(isinstance(g, str) and '<+input>' not in g for g in groups)
    if portable:
        assert groups == ['account.<APPROVED_RELEASE_GROUP>']
    else:
        assert all('<' not in g and '>' not in g for g in groups)


def ordered(nodes):
    return [(n.get('stage') or n['insert'])['identifier'] for n in nodes]


def deployment_nodes(nodes):
    for node in nodes:
        if 'insert' in node:
            yield from deployment_nodes(node['insert']['stages'])
        elif node['stage'].get('type') == 'Deployment':
            yield node['stage']


def required_condition(ids):
    return ' && '.join(f'<+pipeline.stages.{name}.status> == "SUCCEEDED"' for name in ids)


def check_parent(spec, portable=False):
    assert spec['allowStageExecutions'] is False
    assert ordered(spec['stages']) == ['Dev','Approve_Staging','Staging','Approve_Prod','Prod']
    for row in spec['stages']:
        s = row.get('stage', {})
        if s.get('type') == 'Approval':
            approval_contract(s, portable)
        if s.get('template') or s.get('type') == 'Deployment':
            if s['identifier'] in ('Staging','Prod'):
                ids = ['Dev','Approve_Staging'] if s['identifier'] == 'Staging' else ['Dev','Approve_Staging','Staging','Approve_Prod']
                assert s['when'] == {'pipelineStatus': 'Success', 'condition': required_condition(ids)}
            if s.get('template') and s['identifier'] in ('Staging','Prod'):
                assert s['template']['templateInputs']['spec']['service'] == {'useFromStage': {'stage': 'Dev'}}


templates = {}
for file in list((root/'stages').glob('*.yaml')) + list((root/'pipelines').glob('*.yaml')):
    template = yaml.safe_load(file.read_text())['template']
    assert template['versionLabel'] == '0.1.0'
    templates[template['identifier']] = template
    if template['type'] == 'Pipeline':
        check_parent(template['spec'], portable=True)

expected_paths = {
    'ecs_rolling_stage': ['EcsRollingDeploy','Verify'],
    'ecs_canary_stage': ['EcsCanaryDeploy','Verify','EcsCanaryDelete','EcsRollingDeploy'],
    'ecs_blue_green_stage': ['EcsBlueGreenCreateService','Verify','EcsBlueGreenSwapTargetGroups'],
}
for identifier, types in expected_paths.items():
    s = templates[identifier]['spec']
    assert [x['step']['type'] for x in s['spec']['execution']['steps']] == types
    verify = s['spec']['execution']['steps'][1]['step']
    mode = {'ecs_rolling_stage':'Rolling','ecs_canary_stage':'Canary','ecs_blue_green_stage':'Bluegreen'}[identifier]
    assert verify['spec']['type'] == mode and verify['timeout'] == '2h'
    assert verify['spec']['spec'] == {'sensitivity':'HIGH','duration':'15m'}
    assert verify['spec']['monitoredService'] == {'type':'Default','spec':{}}
    assert 'failureStrategies' not in verify
    assert s['when'] == {'pipelineStatus':'Success'}
    assert s['failureStrategies'][0]['onFailure']['action']['type'] == 'StageRollback'
    assert s['spec']['execution']['rollbackSteps']
assert templates['ecs_blue_green_stage']['spec']['spec']['execution']['steps'][2]['step']['spec']['doNotDownsizeOldService'] is False

for file in root.rglob('*.yaml'):
    text = file.read_text()
    assert all(term not in text for term in ('orgIdentifier:', 'projectIdentifier:', 'ecs_minimal_', 'ShellScript', 'ecs_require_success', 'experian', 'ECS_Service_One'))
    assert 'account.' not in text.replace('account.<APPROVED_RELEASE_GROUP>', '')
    for ref, version in re.findall(r'templateRef: (\S+)\s+versionLabel: (\S+)', text):
        assert ref in templates and version == '0.1.0', (file, ref, version)
assert not (root/'minimal').exists()
assert not list(root.rglob('*|*'))

if len(sys.argv) > 1:
    evidence = json.loads(Path(sys.argv[1]).read_text())
    assert len(evidence) == 6
    for item in evidence:
        assert item['saved']['entityValidityDetails']['valid'] is True
        assert item['saved']['storeType'] == 'INLINE'
        saved = yaml.safe_load(item['saved']['yamlPipeline'])['pipeline']
        resolved = yaml.safe_load(item['resolved']['resolvedTemplatesPipelineYaml'])['pipeline']
        if 'template' in saved:
            parent = templates[saved['template']['templateRef']]
            assert parent['type'] == 'Pipeline'
            check_parent(resolved)
            inputs = yaml.safe_load(item['inputs']['inputSetTemplateYaml'])
            assert 'HarnessApproval' not in json.dumps(inputs)
            assert 'userGroups' not in json.dumps(inputs)
            # Propagated services need no second artifact/service prompt.
            if saved['template']['templateRef'] != 'ecs_stage_insert_delivery':
                for row in inputs['pipeline']['template']['templateInputs']['stages']:
                    spec = row['stage']['template']['templateInputs']['spec']
                    assert ('service' in spec) == (row['stage']['identifier'] == 'Dev')
                for s in deployment_nodes(resolved['stages']):
                    if s['identifier'] in ('Staging','Prod'):
                        assert s['spec']['service']['useFromStage'] == {'stage':'Dev'}
        else:
            assert len(resolved['stages']) == 1
            assert item['inputs']['inputSetTemplateYaml'] is None
        for s in deployment_nodes(resolved['stages']):
            assert s['spec']['deploymentType'] == 'ECS'
            assert s['when']['pipelineStatus'] == 'Success'
            assert s['failureStrategies'][0]['onFailure']['action']['type'] == 'StageRollback'
            execution = s['spec']['execution']
            assert any(execution == t['spec']['spec']['execution'] for t in templates.values() if t['type'] == 'Stage')
    print('PASS: six saved INLINE consumers, expanded approvals/CV/rollback and service propagation/runtime input contracts')
print(f'PASS: canonical references, approvals, portable inputs and {cases} strategy/CV-failure/rollback scenarios')

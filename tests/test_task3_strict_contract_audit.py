import json
import zipfile

from scripts.task3_strict_contract_audit import audit_archive
from tests.test_task3_arm_d_plus import finding, unit


def test_audit_reads_recorded_outputs_without_inference_and_counts_overlapping_failures(tmp_path):
    u = unit(); u['level'] = 1
    f = {**finding(), 'error': 'Implementation behavior violating a requirement, with relevant condition',
         'evidence': 'invented expression'}
    r = {'sample_id': u['sample_id'], 'status': 'resolved', 'stage1': {'findings': [f]}}
    calls = [{'sample_id': u['sample_id'], 'stage': 'taxonomy', 'attempt': attempt,
              'raw_text': '{broken', 'input_tokens': 5, 'output_tokens': 2} for attempt in (0, 1)]
    archive = tmp_path/'audit.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('units.private.json', json.dumps([u]))
        z.writestr('results.private.json', json.dumps([r]))
        z.writestr('attempts.jsonl', '\n'.join(json.dumps(c) for c in calls))
    result = audit_archive(archive)
    assert result['new_inference_performed'] is False
    assert result['placeholder_findings'] == result['nonverbatim_findings'] == 1
    assert result['samples_rejected_by_current_contract'] == 1
    assert result['invalid_json_responses'] == 2
    assert result['identical_retry_responses'] == 1
    assert result['level1_renderer_calls_in_recording'] == 0

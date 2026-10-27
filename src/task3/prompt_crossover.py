"""Bounded prompt-crossover integrity; historical native components remain unchanged."""
from copy import deepcopy
import json
from importlib.metadata import version
from pathlib import Path
import platform
import subprocess
from src.task3.sft_v1 import INPUT_KEYS, native_prompt, read_jsonl, sha256
from src.task3.sft_v1_experiment import Journal
from src.task3.sft_v1_runtime import digest
from src.task3.sft_v3 import REVIEW_POLICY as V3_REVIEW_POLICY

REPO = Path(__file__).resolve().parents[2]
CELL_IDS = ('v2-old','v2-v3','v3-old','v3-v3')
AXES = ('diagnosis_supported','coverage','factual_fidelity','location_and_condition',
        'disclosure_compliance','required_content','l3_repair_direction','l4_usefulness','vietnamese_compliance')
REVIEW_POLICY = deepcopy(V3_REVIEW_POLICY)
REVIEW_POLICY.update(version='prompt-crossover-official-separated-content-v1', axes=list(AXES),
    disclosure_compliance='Only disclosure boundaries: L1 status/praise without location/cause/repair; L2 diagnostic location/cause without concrete repair/code; L3 no complete solution; L4 solution/code permitted. False clean assessment can pass boundaries but fails diagnostic correctness.',
    required_content='Separate content-type gate: actual faulty L2 needs location and causal diagnostic content; actual faulty L3 needs diagnostic content plus a repair direction. Correctness of these claims/hints is assessed independently. Truthful clean status needs no fictitious defect/repair; L1 status only and L4 useful content assessed separately.',
    historical_reviews='Evidence only; adjudicate all four cells anew under this single frozen rubric. Do not copy historical verdicts.',
    invalid='all nine semantic axes not_evaluable; code uncertain; every invalid remains in all primary denominators',
    example_selection='deterministic sorted source/Level with family diversity, all cases published; never choose by model identity')


class CrossoverJournal(Journal):
    def __init__(self,path,fresh_cells,expected_ids):
        super().__init__(path)
        self.fresh_cells=tuple(fresh_cells);self.expected_ids=set(expected_ids)
        if (len(set(self.fresh_cells))!=len(self.fresh_cells) or not set(self.fresh_cells)<=set(CELL_IDS)
                or not self.expected_ids or len(self.expected_ids)>80):
            raise ValueError('invalid frozen crossover budget')

    def reserve(self,key,budget=None):
        parts=key.split('/')
        if len(parts)!=2 or parts[0] not in self.fresh_cells or parts[1] not in self.expected_ids:
            raise ValueError('foreign target or reused cell')
        reserved=self.reserved()
        if key in reserved:raise ValueError('generation already reserved')
        if (len(reserved)>=len(self.fresh_cells)*len(self.expected_ids) or len(reserved)>=320
                or sum(k.startswith(parts[0]+'/') for k in reserved)>=len(self.expected_ids)):
            raise ValueError('frozen crossover call ceiling exhausted')
        self.append(dict(type='generation_reserved',key=key))


def call_state(journal,key):
    completed=[e['result'] for e in journal.events() if e.get('type')=='generation_completed' and e.get('key')==key]
    if len(completed)>1:raise ValueError('duplicate completed call')
    reserved=key in journal.reserved()
    if completed:
        if not reserved:raise ValueError('completion without reservation')
        return 'completed',completed[0]
    return ('uncertain',None) if reserved else ('fresh',None)


def prompt_examples(records,root,labels):
    examples=[]
    for row in records:
        x=row['input']
        if set(x)!=INPUT_KEYS:raise ValueError('input whitelist violation')
        level=x['target_feedback_level']
        if type(level)is not int or level not in (1,2,3,4) or x['language']!='cpp11':raise ValueError('input Level/language')
        examples.append(dict(example_id=row['sample_id'],sample_id=row['source_id'],level=level,prompt=native_prompt(root,x,labels)))
    if len({e['example_id'] for e in examples})!=len(examples):raise ValueError('duplicate input ID')
    return examples


def validate_population(rows,examples):
    expected={e['example_id']:(e['sample_id'],e['level']) for e in examples}
    if len(expected)!=len(examples) or len(rows)!=len(expected):raise ValueError('requested-ID coverage')
    observed={}
    for r in rows:
        eid=r['example_id']
        if eid in observed or eid not in expected or (r['sample_id'],r['level'])!=expected[eid]:
            raise ValueError('duplicate/foreign ID or source/Level mismatch')
        observed[eid]=True
    if set(observed)!=set(expected):raise ValueError('requested-ID coverage')
    return True


def validate_durable_rows(rows,examples,journal,cell):
    expected={e['example_id']:(e['sample_id'],e['level']) for e in examples};seen=set()
    for row in rows:
        eid=row['example_id']
        if eid in seen or eid not in expected or (row['sample_id'],row['level'])!=expected[eid]:
            raise ValueError('durable ID/source/Level changed')
        seen.add(eid);state,result=call_state(journal,cell+'/'+eid)
        if state=='completed':
            if {k:v for k,v in row.items() if k!='utc'}!=result:raise ValueError('durable response differs from completed journal')
        elif not (state=='uncertain' and row.get('call_count_uncertain') is True and row['status']=='missing'
                  and row.get('finish_reason')=='interrupted_unknown' and row['parsed']is None and row['raw']==''):
            raise ValueError('durable response lacks a completed or uncertain reservation')
    return True


def validate_runtime_profile(profile):
    if (profile['active_adapters']!=['default'] or profile['adapter_names']!=['default'] or not profile['all_modules_eval']
            or profile['attention']!='sdpa' or profile['lora_dtypes']!={'torch.float32':392}
            or profile['compute_type_flags']!={'True':196}
            or set(profile['parameter_dtypes'])!={'torch.uint8','torch.float32'} or profile['model_config_use_cache']is not False
            or profile['generation_use_cache']is not True):raise ValueError('loaded native/adapter profile differs')
    q=profile['quantization']
    if q!=dict(linear4bit_modules=196,compute_dtypes={'torch.bfloat16':196},storage_dtypes={'torch.uint8':196},quant_types={'nf4':196},nested=True):
        raise ValueError('loaded quantization profile differs')
    generation=profile['generation_config']
    if generation['repetition_penalty']!=1.1 or generation.get('cache_implementation')is not None:raise ValueError('loaded generation profile differs')
    return True


def verify_hashes(root,entries):
    root=Path(root).resolve()
    for name,expected in entries.items():
        p=(root/name).resolve()
        if not p.is_relative_to(root):raise ValueError('invalid frozen path: '+name)
        if not p.is_file() or sha256(p)!=expected:raise ValueError('frozen file changed: '+name)
    return True


def verify_snapshot_hashes(snapshot,entries):
    snapshot=Path(snapshot).resolve();blobs=(snapshot.parent.parent/'blobs').resolve()
    for name,expected in entries.items():
        logical=snapshot/name
        if Path(name).is_absolute() or '..' in Path(name).parts:raise ValueError('invalid snapshot path')
        physical=logical.resolve()
        if not (physical.is_relative_to(snapshot) or physical.is_relative_to(blobs)):
            raise ValueError('invalid snapshot blob path: '+name)
        if not physical.is_file() or sha256(physical)!=expected:raise ValueError('frozen snapshot file changed: '+name)
    return True


def preserve(out):
    initial=json.loads((out/'initial-workspace-state.json').read_text())
    if (subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()!=initial['head']
            or subprocess.check_output(['git','branch','--show-current'],cwd=REPO,text=True).strip()!=initial['branch']):
        raise ValueError('workspace HEAD/branch changed')
    verify_hashes(REPO,initial['files'])
    return dict(passed=True,preexisting_files=len(initial['files']),head=initial['head'],branch=initial['branch'],
                root_predictions_sha256=sha256(REPO/'predictions.json'))


def verify_run(out,preserve=False):
    out=Path(out).resolve();manifest=json.loads((out/'manifest.json').read_text())
    if sha256(out/'manifest.json')!=json.loads((out/'manifest.sha256.json').read_text())['sha256']:
        raise ValueError('crossover manifest seal changed')
    verify_hashes(REPO,manifest['code_files'])
    verify_hashes(REPO,manifest['historical_bindings'])
    verify_hashes(out,manifest['input_files'])
    for cell in manifest['cells'].values():verify_hashes(REPO,cell['adapter_files'])
    runtime=manifest['runtime'];loader=runtime['loader_manifest'];snapshot=Path(loader['config']['tokenizer_local'])
    verify_snapshot_hashes(snapshot,runtime['common_profile']['tokenizer']['files'])
    verify_snapshot_hashes(snapshot,loader['model_files'])
    for name,expected in loader['versions'].items():
        if version(name)!=expected:raise ValueError('current dependency changed: '+name)
    for name,expected in runtime['dependency_source_files'].items():
        if sha256(Path(name))!=expected:raise ValueError('current dependency implementation changed: '+name)
    import torch
    hw=runtime['hardware']
    if platform.python_version()!=hw['python'] or torch.__version__!=hw['torch'] or torch.version.cuda!=hw['cuda_build']:
        raise ValueError('current Python/PyTorch/CUDA build changed')
    current_gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,driver_version,uuid,pci.bus_id','--format=csv,noheader'],text=True).strip()
    if current_gpu!=hw['gpu'] or torch.cuda.device_count()!=hw['device_count']:raise ValueError('current GPU/driver identity changed')
    result=dict(passed=True)
    if preserve:result['preservation']=globals()['preserve'](out)
    return result

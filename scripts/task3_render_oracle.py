#!/usr/bin/env python3
"""Development-only deterministic oracle rendering; no model or public inference."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.task3.cli import verify_prepared
from src.task3.dataset import load_prepared, write_json
from src.task3.diagnosis import attach_compiler_evidence
from src.task3.oracle_findings import load_reviewed_findings
from src.task3.renderer import render_findings, validate_rendered
from src.task3.submission import validate_submission
from src.utils.config import load_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--findings', required=True)
    parser.add_argument('--split', choices=('real-train','real-val'), default='real-val')
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    output = Path(args.output_dir)
    repo = Path(__file__).resolve().parents[1]
    if not output.resolve().is_relative_to(repo / 'outputs'):
        parser.error('private oracle artifacts must stay under ignored repository outputs/')
    if output.exists():
        parser.error('output directory already exists; preserve prior artifacts')
    config = load_config(args.config)
    data = Path(config.get('data_dir','data/processed/task3'))
    manifest_sha = verify_prepared(data)
    records = attach_compiler_evidence(load_prepared(data,args.split),config)
    findings = load_reviewed_findings(args.findings,records)
    documents = [render_findings(record,findings[record.sample_id]) for record in records]
    checks = [validate_rendered(r,findings[r.sample_id],d) for r,d in zip(records,documents)]
    predictions = [{'sample_id':r.sample_id,'output':{'taxonomy_error':r.gold_taxonomy,'feedback':d['feedback']}} for r,d in zip(records,documents)]
    output.mkdir(parents=True)
    write_json(output/'documents.json',documents)
    write_json(output/'predictions.json',predictions)
    validation = validate_submission(output/'predictions.json',{r.sample_id:r.target_feedback_level for r in records})
    files = [repo/'src/task3'/name for name in ('renderer.py','adequacy.py','oracle_findings.py','compiler.py','diagnosis.py')]
    write_json(output/'run.json',{'condition':'approved_oracle_diagnostic_only_not_public',
        'model_called':False,'programs_executed':False,'taxonomy_is_copied_gold_not_predicted':True,
        'git_worktree_dirty':bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],text=True).strip()),
        'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'implementation_sha256':{str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files + [Path(__file__).resolve()]},
        'config':config,'data_manifest_sha256':manifest_sha,
        'findings_sha256':hashlib.sha256(Path(args.findings).read_bytes()).hexdigest(),
        'review_approval':json.loads(Path(args.findings).read_text())['review_approval'],
        'selected_sample_ids':[r.sample_id for r in records],'checks':checks,'validator':validation,
        'limitations':'Factual support conditional on reviewed input. No independent semantic verification or inferred findings.'})
    print(json.dumps({'status':'complete_oracle_render','records':len(records),'model_called':False}))


if __name__=='__main__':
    try:
        main()
    except (ValueError,RuntimeError,FileNotFoundError) as exc:
        raise SystemExit(str(exc)) from None

"""Verify a frozen external evaluation plan; never infer acceptance from file presence."""
import json
from pathlib import Path
from mortgage_risk.artifact_integrity import verify_manifest, safe_path


def check(root):
    root=Path(root).resolve()
    protocol='configs/external_evaluation.json'
    cfg=json.loads((root/protocol).read_text())
    required=[protocol,cfg['candidate'],cfg['benchmark'],cfg['development_result']]
    verify_manifest(root,root/'configs/external_evaluation_integrity.json',required)
    source=safe_path(root,cfg['expected_source'])
    return {'status':'source_present_validation_required' if source.is_file() else 'waiting_for_reserved_cohort',
            'frozen_inputs':'pass','expected_source':str(source),'cohort':cfg['cohort'],
            'external_evaluation_completed':False,'model_promoted':False}


if __name__=='__main__':
    print(json.dumps(check(Path(__file__).resolve().parents[2]),indent=2))

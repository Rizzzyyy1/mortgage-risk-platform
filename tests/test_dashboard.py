import hashlib
import json
from pathlib import Path
import pytest
from mortgage_risk.dashboard import load_payload, sanitize
from mortgage_risk.artifact_integrity import create_manifest

@pytest.fixture
def evidence(tmp_path):
    (tmp_path/'configs').mkdir()
    reports={
      'eligibility':{'status':'pass','eligibility_counts':[{'records':2}], 'monthly_summary':[{'reporting_month':'2020-01-01','records':2,'reported_balance':'12.30'}]},
      'descriptive':{'status':'pass','counts':{'records':2},'monthly':[{'reporting_month':'2020-01-01','records':2,'reported_balance':'12.30'}]},
      'benchmark':{'status':'pass','historical_12m':{}}, 'model':{'status':'pass'},
      'stress':{'status':'pass','baseline':{'remaining_life_expected_loss':'1.10'},'adverse':{'remaining_life_expected_loss':'2.20'}}}
    paths={};manifest={}
    for name,value in reports.items():
        p=tmp_path/(name+'.json');p.write_text(json.dumps(value));paths[name]=p.name
        manifest[name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    (tmp_path/'configs/consolidated_validation.json').write_text(json.dumps({'reports':paths}))
    (tmp_path/'validation.json').write_text(json.dumps({'status':'pass','input_manifest':manifest}))
    config=tmp_path/'config.json';config.write_text(json.dumps({'validation_report':'validation.json','integrity_manifest':'integrity.json'}))
    for name,amount in [('baseline','1.10'),('adverse','2.20')]:
        (tmp_path/(name+'_schedule.json')).write_text(json.dumps([{'month':1,'expected_loss':amount}]))
    (tmp_path/'sensitivity.json').write_text('[]')
    required=list(paths.values())+['validation.json','baseline_schedule.json','adverse_schedule.json','sensitivity.json']
    (tmp_path/'integrity.json').write_text(json.dumps(create_manifest(tmp_path,required)))
    return tmp_path,config

def test_dashboard_reconciles_saved_aggregates(evidence):
    payload=load_payload(*evidence)
    assert payload['loss_curve']==[{'month':1,'baseline':1.1,'adverse':2.2}]
    assert payload['counts']['records']==2

def test_dashboard_rejects_changed_accepted_report(evidence):
    root,config=evidence
    p=root/'model.json';p.write_text('{"status":"pass","changed":true}')
    with pytest.raises(ValueError,match='integrity'):load_payload(root,config)

def test_dashboard_rejects_changed_schedule(evidence):
    root,config=evidence
    (root/'baseline_schedule.json').write_text('[{"expected_loss":"9.99"}]')
    with pytest.raises(ValueError,match='integrity'):load_payload(root,config)

def test_dashboard_strips_internal_paths_without_mutating_input():
    raw={k:{'output_directory':'private','config':{},'metric':2} for k in ['model','stress','validation']}
    cleaned=sanitize(raw)
    assert all(value=={'metric':2} for value in cleaned.values())
    assert raw['model']['output_directory']=='private'


def test_dashboard_rejects_modified_sensitivity(evidence):
    root,config=evidence
    (root/'sensitivity.json').write_text('[{"driver":"lgd","value":999}]')
    with pytest.raises(ValueError,match='integrity'):load_payload(root,config)


def test_dashboard_requires_complete_input_manifest(evidence):
    root,config=evidence
    p=root/'integrity.json';manifest=json.loads(p.read_text())
    del manifest['files']['sensitivity.json'];p.write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='cover'):load_payload(root,config)


def test_dashboard_rejects_nonconsecutive_schedule_even_if_resealed(evidence):
    root,config=evidence
    p=root/'baseline_schedule.json';p.write_text('[{"month":2,"expected_loss":"1.10"}]')
    manifest=root/'integrity.json'
    required=json.loads(manifest.read_text())['files'].keys()
    manifest.write_text(json.dumps(create_manifest(root,required)))
    with pytest.raises(ValueError,match='Nonconsecutive'):load_payload(root,config)


def test_dashboard_rejects_nonfinite_loss_even_if_resealed(evidence):
    root,config=evidence
    (root/'baseline_schedule.json').write_text('[{"month":1,"expected_loss":"NaN"}]')
    manifest=root/'integrity.json'
    required=json.loads(manifest.read_text())['files'].keys()
    manifest.write_text(json.dumps(create_manifest(root,required)))
    with pytest.raises(ValueError,match='Invalid schedule'):load_payload(root,config)

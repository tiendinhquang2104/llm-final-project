"""Metadata-only historical evaluation exclusion; no public source reads."""
def historical_overlap(train, historical):
 def identity(row):
  return {'sample_id':row['sample_id'],'group':row.get('group',row.get('group_key')),
          'code_identity':row.get('code_identity',row.get('code_hash')),
          'renamed_identity':row.get('renamed_identity',row.get('renamed_code_hash'))}
 matches=[]
 for t in train:
  a=identity(t)
  for h in historical:
   b=identity(h);keys=[k for k in a if a[k] and b[k] and a[k]==b[k]]
   if keys:matches.append({'train_id':a['sample_id'],'historical_id':b['sample_id'],'matched_on':keys})
 return matches

def load_historical_evaluations(repo):
 """Read persisted R15/R16/R17 selection metadata, including renamed identities."""
 import json
 from pathlib import Path
 root=Path(repo);rows=[]
 for name in ('round15','round16'):
  path=root/'outputs/task3'/name/'development-selection.json'
  if not path.is_file():raise ValueError('missing historical selection '+str(path))
  rows.extend({**r,'round':name} for r in json.loads(path.read_text())['selected_records'])
 path=root/'outputs/task3/round17/freeze.json'
 if not path.is_file():raise ValueError('missing historical R17 freeze')
 for r in json.loads(path.read_text())['selection']['selection_identity']:
  rows.append({'sample_id':r['id'],'group':r['group'],'code_identity':r['code'],'renamed_identity':r['renamed'],'round':'round17'})
 return rows

def require_historical_isolation(train, repo):
 matches=historical_overlap(train,load_historical_evaluations(repo))
 if matches:raise ValueError('historical evaluation leakage: '+str(matches))

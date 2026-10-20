"""Fixed-label taxonomy scoring with explicit abstention, never exported as []."""
from src.synth.taxonomy import LABEL_SPACE
from src.task3.schema import validate_taxonomy

def taxonomy_metrics(gold, outputs):
 per={l:{'tp':0,'fp':0,'fn':0,'support':0} for l in LABEL_SPACE};exact=completed=0
 for sid,truth in gold.items():
  actual=set(validate_taxonomy(truth));out=outputs.get(sid)
  predicted=set(validate_taxonomy(out['taxonomy_error'])) if out is not None else set()
  # The empty set above is an internal no-positive-decision score, not a
  # successful clean prediction. Abstention never earns exact-set credit.
  if out is not None:
   completed+=1;exact+=actual==predicted
  for label,counts in per.items():
   counts['support']+=label in actual;counts['tp']+=label in actual&predicted
   counts['fp']+=label in predicted-actual;counts['fn']+=label in actual-predicted
 for c in per.values():
  c['precision']=c['tp']/(c['tp']+c['fp']) if c['tp']+c['fp'] else 0
  c['recall']=c['tp']/(c['tp']+c['fn']) if c['tp']+c['fn'] else 0
  c['f1']=2*c['tp']/(2*c['tp']+c['fp']+c['fn']) if 2*c['tp']+c['fp']+c['fn'] else 0
 tp=sum(c['tp'] for c in per.values());fp=sum(c['fp'] for c in per.values());fn=sum(c['fn'] for c in per.values())
 return {'requested':len(gold),'completed':completed,'unresolved':len(gold)-completed,'micro_f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0,'macro_f1':sum(c['f1'] for c in per.values())/len(LABEL_SPACE),'exact_set_count':exact,'exact_set_rate':exact/len(gold) if gold else 0,'tp':tp,'fp':fp,'fn':fn,'per_label':per}

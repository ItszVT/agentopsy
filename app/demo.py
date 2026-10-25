"""Clearly labeled synthetic examples for UI exploration, not benchmark evidence."""
from datetime import datetime, timedelta, timezone

TASKS = [
 ('Fix authentication redirect','Coding','unsolved',47,3,'Terminus2','Unsolved benchmark task'),
 ('Refactor CSV ingestion','Coding','solved',29,0,'mini-SWE-agent',''),
 ('Repair failing unit tests','Testing','unsolved',84,5,'OpenHands','Annotated incorrect stages'),
 ('Update README commands','Documentation','solved',18,0,'SWE-agent',''),
 ('Resolve dependency lock conflict','Dependency','unsolved',108,4,'Terminus2','Long trajectory'),
 ('Improve dashboard performance','Performance','solved',36,1,'OpenHands','Annotated incorrect stages'),
 ('Build a pagination endpoint','API','solved',52,0,'mini-SWE-agent',''),
 ('Debug CLI installation','Tooling','unsolved',121,8,'OpenHands','Long trajectory'),
 ('Patch request validation','Security','solved',64,2,'Terminus2','Annotated incorrect stages'),
 ('Generate integration tests','Testing','unsolved',76,3,'SWE-agent','Unsolved benchmark task'),
 ('Fix config file parsing','Tooling','solved',27,0,'mini-SWE-agent',''),
 ('Repair database migration','Database','unsolved',93,6,'OpenHands','Annotated incorrect stages'),
]


def demo_cases():
    now=datetime(2026,10,24,tzinfo=timezone.utc)
    results=[]
    for i,(task,category,outcome,steps,bad,agent,signal) in enumerate(TASKS):
        signals=[]
        if outcome!='solved': signals.append('Unsolved benchmark task')
        if bad: signals.append('Annotated incorrect stages')
        if steps>=100: signals.append('Long trajectory')
        events=[]
        for k in range(1,7):
            issue = bad and k in (3,5)
            events.append({'index':k,'label':f'Stage {k}',
                'detail':f'Illustrative steps {1+(k-1)*steps//6} to {k*steps//6}',
                'kind':'stage','status':'suspected' if issue else 'recorded'})
        results.append({'id':f'demo-{i+1:02d}','source':'Demo simulation',
          'agent':agent,'model':'Synthetic','task':task,'category':category,
          'outcome':outcome,'step_count':steps,'issue_count':bad,
          'incorrect_stages':bad, 'signals':signals,'events':events,
          'is_demo':True,'note':'Synthetic demonstration. Not a real Tracebench result. Stage details are illustrative.',
          'created_at':(now-timedelta(days=i)).isoformat()})
    return results

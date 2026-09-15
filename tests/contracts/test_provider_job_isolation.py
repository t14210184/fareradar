import json, pathlib, subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]

def test_source_and_provider_jobs_are_isolated_and_background_is_explicit():
    p=subprocess.run(['node','tests/node_provider_job_isolation.mjs'],cwd=ROOT,text=True,capture_output=True,check=True)
    x=json.loads(p.stdout)
    assert x['backgroundBlocked'] is True
    assert x['sourceJobs']==['source-job']
    assert x['revokedBackgroundJobs']==[]
    assert x['providerJobs']==[x['userEnq']['job_id']]
    assert x['providerModes']==['USER_REQUEST']
    assert x['sourceTarget']=='EXTERNAL_HEAVY' and x['providerApiCount']==2

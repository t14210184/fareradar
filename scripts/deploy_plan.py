from __future__ import annotations
import json
from production_preflight import evaluate
ORDERED_SHARED_STEPS=[
  'CREATE_OR_ATTACH_GITHUB_REMOTE_AND_READ_BACK_EXACT_HEAD',
  'PROVISION_CLOUDFLARE_AUTH_AND_READ_BACK_IDENTITY',
  'CREATE_OR_BIND_D1_AND_READ_BACK_DATABASE_ID',
  'APPLY_MIGRATIONS_AND_REGISTRY_SEEDS_WITH_PROVIDER_READBACK',
  'PROVISION_REQUIRED_SECRETS_WITH_PROVIDER_READBACK',
  'DEPLOY_WORKER_AND_READ_BACK_VERSION_ID_AND_HEALTH',
  'RUN_SHADOW_AND_ACCUMULATE_14_DAY_LABELED_CORPUS',
  'RE_RUN_PRODUCTION_PREFLIGHT'
]
def plan():
    state=evaluate()
    return {
      'mutation_allowed': False,
      'reason':'READ_ONLY_DEPLOY_PLAN_REQUIRES_PROVIDER_MUTATION_PERMIT',
      'code_ready':state['code_ready'],
      'production_ready':state['production_ready'],
      'blockers':state['blockers'],
      'ordered_shared_steps':ORDERED_SHARED_STEPS
    }
if __name__=='__main__': print(json.dumps(plan(),ensure_ascii=False,indent=2))

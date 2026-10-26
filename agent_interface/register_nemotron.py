"""Register the already-cached Nemotron checkpoint; never download weights."""
import json
from pathlib import Path

base = Path(__file__).resolve().parent
kit = Path.home()/'Desktop/build-a-claw'
model_id = 'nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-NVFP4'
cache = Path.home()/'.cache/huggingface/hub'/('models--'+model_id.replace('/','--'))
ref = cache/'refs/main'
snapshots = [cache/'snapshots'/ref.read_text().strip()] if ref.exists() else sorted((cache/'snapshots').glob('*'))
complete = []
for path in snapshots:
    index = path/'model.safetensors.index.json'
    if index.exists():
        shards = set(json.loads(index.read_text())['weight_map'].values())
        if all((path/name).is_file() for name in shards):
            complete.append(path)
if not complete:
    raise SystemExit('No complete cached Nemotron checkpoint found.')
path = complete[-1]
runtime = kit/'runtime/restored/vllm/bin/vllm'
config = {'enabled':True, 'model_id':model_id, 'snapshot':path.name,
          'path':str(path), 'context_window':131072, 'max_tokens':16000,
          'argv':[str(runtime),'serve','{model_path}','--host','127.0.0.1','--port','8000',
                  '--served-model-name','{model_id}','--trust-remote-code',
                  '--gpu-memory-utilization','0.7','--max-model-len','131072',
                  '--max-num-seqs','2','--moe-backend','marlin',
                  '--limit-mm-per-prompt','{"image":0,"video":0,"audio":0}',
                  '--enable-prefix-caching','--reasoning-parser','nemotron_v3',
                  '--enable-auto-tool-choice','--tool-call-parser','qwen3_coder'],
          'env':{'PATH':str(runtime.parent)+':/usr/local/cuda/bin:/usr/local/bin:/usr/bin:/bin',
                 'CUDA_HOME':'/usr/local/cuda','HF_HUB_OFFLINE':'1'}}
extra = base/'models.extra.json'
configs = json.loads(extra.read_text()) if extra.exists() else {}
configs['nemotron'] = config
extra.write_text(json.dumps(configs,indent=2))
print('Registered cached checkpoint:',model_id,path.name)

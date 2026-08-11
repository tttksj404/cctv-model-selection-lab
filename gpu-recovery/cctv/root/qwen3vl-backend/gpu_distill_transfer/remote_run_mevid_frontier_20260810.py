from pathlib import Path
import hashlib
import json
import runpy
import shutil
import subprocess
import sys

import torch

root = Path('<redacted-local-path>')
shutil.copyfile(
    root / 'evaluate_prid2011_graph_open_set_20260810.py',
    root / 'scripts/evaluate_prid2011_graph_open_set.py',
)
shutil.copyfile(
    root / 'evaluate_mevid_retrieval_frontier_20260810.py',
    root / 'tmp/evaluate_mevid_retrieval_frontier_20260810.py',
)
cache = root / 'experiments/results/mevid_public_full_solider_metric_guarded_tracks_20260731.npz'
output = root / 'tmp/mevid_retrieval_frontier_gpu_20260810.json'
sys.path.insert(0, str(root))
sys.argv = [
    str(root / 'tmp/evaluate_mevid_retrieval_frontier_20260810.py'),
    '--track-cache', str(cache),
    '--output', str(output),
]
runpy.run_path(str(root / 'tmp/evaluate_mevid_retrieval_frontier_20260810.py'), run_name='__main__')
result = json.loads(output.read_text(encoding='utf-8'))
result['execution'] = {
    'location': 'authenticated remote Jupyter GPU workspace',
    'gpu': subprocess.check_output(
        ['nvidia-smi', '--query-gpu=index,name,memory.used,memory.total', '--format=csv,noheader'],
        text=True,
    ).strip(),
    'torch': torch.__version__,
    'cudaAvailable': bool(torch.cuda.is_available()),
    'cudaDevice': torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    'checkpointSha256': result['dataset']['trackCacheSha256'],
}
output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'selected': result['selected'], 'testAbove90': result['testAbove90'], 'execution': result['execution']}, ensure_ascii=False))

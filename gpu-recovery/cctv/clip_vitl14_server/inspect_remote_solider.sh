#!/usr/bin/env bash
set -u
cd <redacted-local-path>
git rev-parse HEAD || true
grep -R -n 'def load_param' model.py model 2>/dev/null | head -20 || true
grep -R -n 'def forward' model/make_model.py model 2>/dev/null | head -20 || true
sed -n '1,240p' model/make_model.py | tail -120
sed -n '340,455p' model/make_model.py
grep -nE 'JPM|MODEL:|NECK_FEAT|REDUCE_FEAT_DIM|FEAT_DIM|TRANSFORMER_TYPE|NAME:' configs/msmt17/swin_base.yml

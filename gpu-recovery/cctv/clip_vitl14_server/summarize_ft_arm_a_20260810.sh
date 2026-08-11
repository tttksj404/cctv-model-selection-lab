#!/usr/bin/env bash
set +e
cd <redacted-local-path>
for file in experiments/results/chirla_identity_heldout_ft_arm_a_*.json; do
  echo "--- $file"
  grep -E '"(rank1|recall_at_5|recallAt5|identity_rank1|identity_recall_at5|identity_mrr|query_count|gallery_identity_count)"' "$file" | head -24
done
exit 0

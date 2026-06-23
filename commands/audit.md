---
description: Score the last assistant turn in the current session transcript for yield-back
---

Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/bin/btwb_score.py" \
  --transcript "<transcript_path from Stop hook or session>" \
  --profile "${CLAUDE_PLUGIN_ROOT}/profiles/default.json" \
  --emit-detail
```

Report score, klass, offenders, and excerpt to the operator.
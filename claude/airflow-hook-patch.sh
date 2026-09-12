#!/bin/bash
# Hook: UserPromptSubmit - suggest the Airflow skill when *genuine* Airflow
# terms appear. Narrowed from the shipped astronomer-data version (removed the
# "af" fragment and generic words like pipeline/workflow/variable/connection/pool
# that caused false positives) and switched to word-boundary matching.
#
# NOTE: this replaces the plugin's own airflow-skill-suggester.sh, which an
# astronomer-data update will overwrite. scripts/claude-env.sh re-applies it.

USER_PROMPT=$(cat)
PROMPT_LOWER=$(echo "$USER_PROMPT" | tr '[:upper:]' '[:lower:]')

# Strong, Airflow-specific signals only, matched at word boundaries (-w).
KEYWORDS_RE='airflow|dags?|dag run|dag runs|dag status|trigger dag|test dag|debug dag|list dags|show dags|get dag|astro dev|task instance|task run|backfill|xcom|scheduler'

if ! echo "$PROMPT_LOWER" | grep -qiwE "$KEYWORDS_RE"; then
    exit 0
fi
if echo "$PROMPT_LOWER" | grep -q "use.*skill\|/data:airflow"; then
    exit 0
fi

cat <<'EOF'
🎯 Airflow operation detected!

IMPORTANT: Use the `/data:airflow` skill for Airflow operations. This skill provides:
- Structured workflow guidance
- Best practices for MCP tool usage
- Routing to specialized skills (testing, debugging, authoring)
- Prevention of bash/CLI antipatterns

Load the skill first: `/data:airflow`

Then proceed with the user's request.
EOF
exit 0

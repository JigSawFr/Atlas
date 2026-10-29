#!/bin/bash
# Says on GitHub when a run went wrong, so it is not missed: an issue
# labelled data-alert (its owner is mailed), or a comment on the one still
# open. Wrong is the job failing, one of its steps that may fail without
# failing it (OUTCOMES: "name=outcome …", as the workflow gives them), or a
# file the guard kept from the last run (ALERTS: the lines tools/build.py's
# publish() wrote). Nothing wrong: nothing said.
#
# Usage (a workflow's last step, `if: always()`, GH_TOKEN with issues: write):
#   JOB_STATUS=${{ job.status }} OUTCOMES="…" ALERTS=<file> tools/alert.sh <workflow's name>
set -u
name=$1
lines=()
[ "${JOB_STATUS:-success}" = success ] || lines+=("- The job ended in **${JOB_STATUS}**.")
for pair in ${OUTCOMES:-}; do
  step=${pair%%=*}; outcome=${pair#*=}
  [ "$outcome" = failure ] && lines+=("- The **${step}** step failed; the run went on without it.")
done
if [ -n "${ALERTS:-}" ] && [ -s "$ALERTS" ]; then
  while IFS= read -r line; do lines+=("- $line"); done < "$ALERTS"
fi
[ ${#lines[@]} -eq 0 ] && { echo "nothing to say"; exit 0; }

run="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}"
body=$(printf '%s run of %s: [its log](%s).\n\n%s\n' "$name" "$(date -u +%Y-%m-%d)" "$run" "$(printf '%s\n' "${lines[@]}")")
gh label create data-alert --color d73a4a --description "A data run went wrong" >/dev/null 2>&1 || true
open=$(gh issue list --label data-alert --state open --json number --jq '.[0].number')
if [ -n "$open" ]; then
  gh issue comment "$open" --body "$body"
else
  gh issue create --title "A data run went wrong ($name, $(date -u +%Y-%m-%d))" --label data-alert --body "$body"
fi

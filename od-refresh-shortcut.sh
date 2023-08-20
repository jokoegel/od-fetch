#!/bin/bash

# Exit on error. Append "|| true" if you expect an error.
set -o errexit
# Exit on error inside any functions or subshells.
set -o errtrace
# Do not allow use of undefined vars. Use ${VAR:-} to use an undefined VAR
set -o nounset
set -o pipefail

# remove echoing directory name on 'cd' command
unset CDPATH
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" # the full path of the directory where the script resides


set -e

OD_FETCH_DIR=${SCRIPT_DIR} #change if script copied to other location
USERNAME="<enter username"
PASSWORD="<enter password>"
CSV_FILE=${SCRIPT_DIR}/od-archive.csv # change to your favorite location (e.g., file share)
PDF_DIR=${SCRIPT_DIR}/od-archive-pdfs # change to your favorite location (e.g., file share)
LOGFILE=${SCRIPT_DIR}/od-fetch.log

cd ${OD_FETCH_DIR}

#virtual environment
source venv/bin/activate

./od-fetch.py --username=${USERNAME} --password=${PASSWORD} --mode=r -c ${CSV_FILE} -o ${PDF_DIR} --logfile=${LOGFILE}


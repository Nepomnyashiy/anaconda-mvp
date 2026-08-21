#!/usr/bin/env bash
set -euo pipefail

if [[ -e .env ]]; then
    printf '%s\n' '.env already exists; refusing to overwrite it.' >&2
    exit 1
fi

cp env.example .env
chmod 600 .env

printf '%s\n' '.env created with placeholders and mode 0600.'
printf '%s\n' 'Replace every placeholder before starting the application.'

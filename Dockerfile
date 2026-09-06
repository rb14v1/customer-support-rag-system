# This repository uses component-specific Dockerfiles.
# The single-component Dockerfile that previously lived here has been
# replaced by the following per-component files:
#
#   API  (Django/Python) : Dockerfile.api
#                          docker build -f Dockerfile.api .
#
#   Web  (React/Vite)    : frontend/Dockerfile
#                          docker build -f frontend/Dockerfile ./frontend
#
# Do NOT add build instructions back to this file.

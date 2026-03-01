FROM python:3.12-slim

WORKDIR /sandbox

# Use existing non-root uid/gid on Debian-based images.
USER 65534:65534

# Run script path provided as first argument, defaulting to /sandbox/script.py.
ENTRYPOINT ["python3", "-I"]
CMD ["/sandbox/script.py"]

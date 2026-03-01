FROM python:3.12-slim

WORKDIR /sandbox

# Install approved science libraries (pinned versions).
RUN python3 -m pip install --no-cache-dir \
    numpy==2.2.3 \
    sympy==1.13.3 \
    pandas==2.2.3

# Use existing non-root uid/gid on Debian-based images.
USER 65534:65534

# Run script path provided as first argument, defaulting to /sandbox/script.py.
ENTRYPOINT ["python3", "-I"]
CMD ["/sandbox/script.py"]

FROM myoung34/github-runner:latest

# Install PMOVES runner Python dependencies (PyYAML, rich, psutil)
# Required by 21+ tools in pmoves/tools/ that use `import yaml`
COPY pmoves/tools/requirements-lite.txt /tmp/requirements-lite.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements-lite.txt && \
    rm /tmp/requirements-lite.txt

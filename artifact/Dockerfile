# Build from the repository root:  docker build -f artifact/Dockerfile -t qtiming-artifact .
# Run:                             docker run --rm qtiming-artifact
# No network is needed at run time. The CSTNU Tool jar and IBM hardware data are NOT included.
FROM python:3.12-slim
WORKDIR /qtiming
COPY . /qtiming
RUN pip install --no-cache-dir -e ".[qiskit,z3,dev]"
CMD ["./artifact/smoke.sh"]

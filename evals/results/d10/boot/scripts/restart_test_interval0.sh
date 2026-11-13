# D: tests/api/test_http_restart.py run as its __main__ (what the pytest wrapper calls) inside the api image, starting its own pgvector container in dind
cd /work/proj3-b
docker run --rm --network host --user root -v /var/run/docker.sock:/var/run/docker.sock -v /usr/local/bin/docker:/usr/local/bin/docker:ro \
  -v /work/proj3-b:/work -w /work -e PYTHONPATH=/work -e SOJAFIT_HTTP_RESTART_RUN=1 -e ANALYSIS_MIN_INTERVAL_SECONDS=0 proj3-b-api:latest python tests/api/test_http_restart.py
echo "exit=$?"

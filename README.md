# Flask API Service Starter

This is a minimal Flask API service starter based on [Google Cloud Run Quickstart](https://cloud.google.com/run/docs/quickstarts/build-and-deploy/deploy-python-service).

## Getting Started

Server should run automatically when starting a workspace. To run manually, run:
```sh
./devserver.sh
```
Github repository

https://github.com/bossprank/wordsenseapi.git

Terminal commands

curl -X POST http://localhost:5000/api/v1/enrich -H "Content-Type: application/json" -d '{"headword": "kamar", "language": "id", "target_language": "en", "categories": ["basic verbs", "drinks"], "force_reenrich": false, "provider": "deepseek"}'

rm -f mylogs/main_app.log && sh devserver.sh >> mylogs/main_app.log 2>&1

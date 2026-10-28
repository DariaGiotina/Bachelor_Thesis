# Skincare Companion (bachelor thesis project)

AI-assisted skincare companion app (React Native + Expo / FastAPI / MongoDB) and an ML study on
questionnaire-augmented skin-concern classification under missing answers.

Informational tool only; not a medical device.

- `app/` React Native (Expo) client
- `api/` backend (FastAPI); `api/ml_service/` serves the exported skin-concern model
  (`uvicorn api.ml_service.app:app --port 8001`, tests `python -m pytest api/tests`)
- `ml/` Python ML environment and experiments
- `docs/` thesis draft, planning documents and journal

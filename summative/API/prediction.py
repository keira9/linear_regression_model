"""Seen API: estimates the loan size a woman entrepreneur in Africa can raise.

Start locally with:  uvicorn prediction:app --reload
"""

import os

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from model_manager import MODEL
from schemas import LoanApplication, LoanEstimate

app = FastAPI(
    title="Seen Loan Size API",
    version="1.0",
    description="Predicts the loan amount (USD) a woman-led business in Africa is likely to raise, "
                "trained on 101,857 women-led Kiva loans. Use /predict for one estimate and /retrain to add new loans.",
)

# ---------------------------------------------------------------------------------------------
# CORS settings
# allow_origins: browsers may call this API only from these pages: the API's own Render address
#   (where Swagger UI runs) and the Flutter web build during development (flutter run -d chrome
#   --web-port 8080). Any other website is blocked. A wildcard "*" would let any site use /retrain
#   from a visitor's browser, so it is not used. Extra origins can be added with the ALLOWED_ORIGINS
#   environment variable on Render, separated by commas.
# allow_methods: only GET (read) and POST (predict, retrain). Nothing in this API edits or deletes.
# allow_headers: only Content-Type (JSON and file uploads), Accept and Authorization.
# allow_credentials: True, so a signed-in dashboard on one of the listed origins could send its
#   cookie or token later. Browsers only allow this together with a fixed origin list.
# The Flutter app on a phone or emulator is not a browser, so CORS never blocks it.
# ---------------------------------------------------------------------------------------------
origins = ["https://seen-loan-api.onrender.com", "http://localhost:8080", "http://127.0.0.1:8080"]
origins += [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Accept", "Authorization"],
    allow_credentials=True,
)


@app.get("/", tags=["about"])
def welcome():
    return {"service": "Seen Loan Size API", "docs": "/docs", "model": MODEL.summary()}


@app.get("/choices", tags=["about"])
def choices():
    """Accepted values for the text inputs of /predict."""
    return {
        "country": MODEL.choices("country"),
        "activity": MODEL.choices("activity"),
        "repayment_interval": MODEL.choices("repayment_interval"),
        "term_in_months": "whole number from 1 to 60",
        "borrower_count": "whole number from 1 to 50",
        "repeat_borrower": "true or false",
    }


@app.get("/model", tags=["about"])
def model_details():
    return MODEL.summary()


@app.post("/predict", response_model=LoanEstimate, tags=["prediction"])
def predict(application: LoanApplication):
    """Estimates the loan size for one woman-led business."""
    applicant = application.model_dump()
    applicant["repeat_borrower"] = int(applicant["repeat_borrower"])
    estimate = MODEL.predict_loan_size(applicant)
    return MODEL.describe(applicant, estimate)


@app.post("/retrain", tags=["retraining"])
def retrain(file: UploadFile = File(..., description="CSV of new loans with the Kiva columns")):
    """Upload a CSV of new loans. The upload itself starts retraining.

    New rows are cleaned like the notebook, 80% join the original training rows and 20% join the test rows.
    The model is fitted again and replaces the current one only if it is not worse on the shared test rows
    and still passes the deployment rule.
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a .csv file.")
    content = file.file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="The file is empty.")
    if len(content) > 15_000_000:
        raise HTTPException(status_code=413, detail="The file is larger than 15 MB.")
    try:
        return MODEL.retrain(content)
    except ValueError as problem:
        raise HTTPException(status_code=400, detail=str(problem)) from problem

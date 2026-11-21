# Seen: loan size estimates for women entrepreneurs in Africa

## Mission and problem
I am building an ML-powered credit model that unlocks capital for women entrepreneurs in emerging markets, because they are not unbankable, just unseen.
Women who run market stalls, farms and small shops often ask for loans without knowing what is realistic for a business like theirs, so requests stall or stay too small.
This project predicts the loan amount (USD) a woman-led business in Africa is likely to raise, from her country, business activity, loan terms, group size and borrowing history.
Loan officers at cooperatives and microfinance partners, and the women themselves, can use it to size a loan request before it is posted.

## Dataset
**Kiva Crowdfunding loans** (`kiva_loans.csv`), released by Kiva for the "Data Science for Good: Kiva Crowdfunding" challenge: https://www.kaggle.com/datasets/kiva/data-science-for-good-kiva-crowdfunding

Each row is a real loan request posted on kiva.org between January 2014 and July 2017, recorded by Kiva's field partners (microfinance institutions, cooperatives and social enterprises) who meet the borrowers. The full file has 671,205 loans and 20 columns: amounts, business activity and sector, country and region, currency, field partner, posting and funding dates, loan term, lender count, tags, borrower genders and repayment schedule. `summative/linear_regression/prepare_data.py` keeps the 173,038 African loans. The notebook then keeps the 101,857 loans led only by women in 24 countries.

## API
**Swagger UI: https://seen-loan-api.onrender.com/docs**

The API runs on Render's free plan, which sleeps after 15 minutes without visits. The first request after that can take up to a minute.
### How to test the API in Swagger

Open the Swagger link above, wait up to a minute if the server is waking up, then try each case:

1. **Valid prediction.** `POST /predict` > Try it out, paste the body below, Execute. Expect `200` with the estimated amount.
   ```json
   {"country": "Kenya", "activity": "Retail", "repayment_interval": "monthly",
    "term_in_months": 12, "borrower_count": 1, "repeat_borrower": false}
   ```
2. **Wrong data type.** Change `"term_in_months"` to `"twelve"`. Expect `422` (validation error), no prediction.
3. **Out-of-range value.** Change `"borrower_count"` to `80` (the limit is 50). Expect `422`.
4. **Missing value.** Delete the `country` line. Expect `422`.
5. **Retraining.** `POST /retrain` > Try it out, choose the file `summative/API/sample_new_loans.csv`, Execute. The upload starts retraining and the response says whether the new model was accepted.
6. **Check the model.** `GET /model` shows the model version and the test scores, so you can see whether retraining changed it.

## Video demo
https://youtu.be/CYPXZEb7Djw

## Running the mobile app
1. Install Flutter (https://docs.flutter.dev/get-started/install) and run `flutter doctor` to check the setup.
2. Start an Android emulator (Android Studio, Device Manager) or an iOS simulator (Mac only), or connect a phone.
3. In a terminal:
   ```bash
   cd summative/FlutterApp/seen_loan_app
   flutter pub get
   flutter run
   ```
   If the `android` or `ios` folder is missing, first run `flutter create --platforms=android,ios --project-name seen_loan_app .` in the same folder.
4. Open https://seen-loan-api.onrender.com/docs once so the server is awake.
5. In the app, fill in the six fields, for example `Kenya`, `Retail`, `monthly`, `12`, `1`, `no`, and tap **Predict**. The estimate, or a message explaining what to fix, appears in the panel at the bottom.

---

## How the model was built

The notebook is `summative/linear_regression/multivariate.ipynb`.

* **Target:** `log(1 + loan_amount)`, because amounts range from 25 to 50,000 dollars and the raw values are very skewed.
* **Inputs:** `country`, `activity`, `repayment_interval`, `term_in_months`, `borrower_count` (women in the loan, from `borrower_genders`) and `repeat_borrower` (from the `#Repeat Borrower` tag).
* **Removed:** `funded_amount` and `lender_count` (only known after funding, so they leak the answer), `sector` (fixed by `activity`), `partner_id` (an anonymous code), and the dates (the data stops in 2017).

| Model | Train MSE | Test MSE | Test R² | Median error |
|---|---|---|---|---|
| **Random forest (saved)** | 0.211 | **0.225** | 0.726 | 26% |
| Decision tree | 0.218 | 0.232 | 0.717 | 27% |
| Linear regression (closed form) | 0.355 | 0.356 | 0.567 | 38% |
| Linear regression (SGD) | 0.355 | 0.356 | 0.567 | 38% |
| Always predict the average | 0.827 | 0.821 | 0.000 | 54% |

The random forest has the lowest test MSE, so it is saved in `summative/API/best_model.pkl` with its preprocessing. The notebook only saves it because it passes a deployment rule: R² of at least 0.60 and an MSE of at most half the baseline.

## API routes

| Route | Method | Purpose |
|---|---|---|
| `/predict` | POST | Estimate for one business: the amount, a likely range and the sector. |
| `/retrain` | POST | Upload a CSV of new loans (Kiva columns). The upload starts retraining. |
| `/choices` | GET | Accepted countries, activities and repayment schedules. |
| `/model` | GET | Current model version, size of the training data and test scores. |
| `/docs` | GET | Swagger UI. |

```json
{"country": "Kenya", "activity": "Retail", "repayment_interval": "monthly",
 "term_in_months": 12, "borrower_count": 1, "repeat_borrower": false}
```

Validation (Pydantic, `summative/API/schemas.py`):
* `term_in_months` must be a whole number from 1 to 60 and `borrower_count` from 1 to 50. Numbers sent as text (`"12"`) are refused.
* `repeat_borrower` must be `true` or `false`.
* `repayment_interval` must be one of four schedules.
* `country` and `activity` must be values the model knows. Capital letters do not matter, and a typo gets the closest matches back.

Wrong types, missing fields, extra fields and out-of-range values all return a 422 error.

**Retraining** (`summative/API/model_manager.py`):
1. The upload is cleaned like the notebook: women-led loans only, terms of 1 to 60 months, known countries and activities.
2. 80% of the new rows join the original training rows and 20% join the test rows.
3. The random forest is fitted again. (If the best model were SGD, it would continue with `partial_fit` instead.)
4. The new model replaces the current one only if it is no worse on the shared test rows and still passes the deployment rule.
5. The old version is kept in `model_archive/`, and every attempt is logged.

`summative/API/sample_new_loans.csv` (June and July 2017) is ready to upload. Render's free plan deletes files written at runtime when the service restarts, so the API then loads the original model from the repository again.

**CORS:** `CORSMiddleware` lists the allowed origins (the Render address and `http://localhost:8080` for Flutter web). It allows only `GET` and `POST`, only the `Content-Type`, `Accept` and `Authorization` headers, and credentials. The comment above it in `prediction.py` explains each choice.

## Running everything locally

```bash
cd summative
uv sync --all-groups                                   # Python 3.12 environment from pyproject.toml + uv.lock
uv run --group notebook jupyter lab linear_regression/multivariate.ipynb
uv run --group dev pytest tests                        # 10 API tests
cd API && uv run uvicorn prediction:app --reload       # http://127.0.0.1:8000/docs
```

`summative/API/requirements.txt` was made with `uv export --format requirements.txt --no-hashes -o API/requirements.txt`.
On Render: Web Service, root directory `summative/API`, build `pip install -r requirements.txt`, start `uvicorn prediction:app --host 0.0.0.0 --port $PORT`.

## Repository layout

```
linear_regression_model/
├── README.md
└── summative/
    ├── pyproject.toml
    ├── uv.lock
    ├── linear_regression/
    │   ├── multivariate.ipynb
    │   ├── prepare_data.py
    │   └── kiva_africa_loans.csv.gz
    ├── API/
    │   ├── prediction.py        routes and CORS
    │   ├── schemas.py           Pydantic request and response models
    │   ├── model_manager.py     prediction and retraining
    │   ├── requirements.txt
    │   ├── best_model.pkl
    │   ├── sample_new_loans.csv
    │   └── data/                training and test rows used by /retrain
    ├── tests/
    └── FlutterApp/
        └── seen_loan_app/
```


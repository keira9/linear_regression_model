import io

import pandas as pd

VALID = {"country": "Kenya", "activity": "Retail", "repayment_interval": "monthly",
         "term_in_months": 12, "borrower_count": 1, "repeat_borrower": False}


def test_prediction_is_returned(api):
    client, _ = api
    response = client.post("/predict", json=VALID)
    assert response.status_code == 200, response.text
    body = response.json()
    low, high = body["likely_range_usd"]
    assert low <= body["estimated_loan_usd"] <= high
    assert body["sector"] == "Retail"


def test_bigger_groups_get_bigger_estimates(api):
    client, _ = api
    one = client.post("/predict", json=VALID).json()["estimated_loan_usd"]
    ten = client.post("/predict", json={**VALID, "borrower_count": 10}).json()["estimated_loan_usd"]
    assert ten > one


def test_spelling_and_case_are_forgiven(api):
    client, _ = api
    response = client.post("/predict", json={**VALID, "country": " kenya ", "activity": "retail", "repayment_interval": "Monthly"})
    assert response.status_code == 200, response.text


def test_wrong_types_are_refused(api):
    client, _ = api
    for change in [{"term_in_months": "twelve"}, {"term_in_months": "12"}, {"borrower_count": 2.5},
                   {"repeat_borrower": "yes"}, {"country": 7}]:
        assert client.post("/predict", json={**VALID, **change}).status_code == 422, change


def test_out_of_range_values_are_refused(api):
    client, _ = api
    for change in [{"term_in_months": 0}, {"term_in_months": 61}, {"borrower_count": 0}, {"borrower_count": 51},
                   {"repayment_interval": "daily"}]:
        assert client.post("/predict", json={**VALID, **change}).status_code == 422, change


def test_unknown_and_missing_values_are_refused(api):
    client, _ = api
    response = client.post("/predict", json={**VALID, "country": "Kenia"})
    assert response.status_code == 422 and "Kenya" in response.text
    no_country = {k: v for k, v in VALID.items() if k != "country"}
    assert client.post("/predict", json=no_country).status_code == 422
    assert client.post("/predict", json={**VALID, "income": 5}).status_code == 422


def test_cors_rules(api):
    client, _ = api
    allowed = client.options("/predict", headers={"Origin": "http://localhost:8080", "Access-Control-Request-Method": "POST",
                                                  "Access-Control-Request-Headers": "content-type"})
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:8080"
    assert allowed.headers.get("access-control-allow-credentials") == "true"
    blocked = client.options("/predict", headers={"Origin": "https://random-site.com", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in blocked.headers
    wrong_method = client.options("/predict", headers={"Origin": "http://localhost:8080", "Access-Control-Request-Method": "DELETE"})
    assert wrong_method.status_code == 400


def test_bad_uploads_are_refused(api):
    client, _ = api
    assert client.post("/retrain", files={"file": ("notes.txt", b"hello", "text/plain")}).status_code == 400
    response = client.post("/retrain", files={"file": ("x.csv", b"a,b\n1,2\n", "text/csv")})
    assert response.status_code == 400


def test_scrambled_amounts_are_rejected(api):
    client, folder = api
    rows = pd.read_csv(folder / "sample_new_loans.csv")
    rows["loan_amount"] = rows["loan_amount"].sample(frac=1, random_state=3).to_numpy() * 20
    buffer = io.BytesIO()
    rows.to_csv(buffer, index=False)
    before = client.get("/model").json()["version"]
    body = client.post("/retrain", files={"file": ("bad.csv", buffer.getvalue(), "text/csv")}).json()
    assert body["accepted"] is False, body
    assert client.get("/model").json()["version"] == before


def test_new_loans_update_the_model(api):
    client, folder = api
    before = client.get("/model").json()
    upload = (folder / "sample_new_loans.csv").read_bytes()
    body = client.post("/retrain", files={"file": ("sample_new_loans.csv", upload, "text/csv")}).json()
    print(body)
    assert body["accepted"] is True, body
    after = client.get("/model").json()
    assert after["version"] == before["version"] + 1
    assert after["trained_on_rows"] > before["trained_on_rows"]
    assert client.post("/predict", json=VALID).json()["model_version"] == after["version"]
    assert (folder / "model_archive" / f"model_v{before['version']}.pkl").exists()

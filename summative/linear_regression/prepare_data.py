"""Builds kiva_africa_loans.csv.gz from the full Kiva file.

Source: kiva_loans.csv from the Kiva "Data Science for Good" release (671,205 loans, 2014 to 2017).
I keep only loans from African countries and drop the free-text "use" column to keep the file small.
Every other column is kept exactly as Kiva published it, so all filtering decisions are visible in the notebook.

Run once:  python prepare_data.py path/to/kiva_loans.csv
"""
import sys

import pandas as pd

AFRICA = {
    "Benin", "Burkina Faso", "Burundi", "Cameroon", "Congo", "Cote D'Ivoire", "Egypt", "Ghana", "Kenya",
    "Lesotho", "Liberia", "Madagascar", "Malawi", "Mali", "Mauritania", "Mozambique", "Namibia", "Nigeria",
    "Rwanda", "Senegal", "Sierra Leone", "Somalia", "South Africa", "South Sudan", "Tanzania",
    "The Democratic Republic of the Congo", "Togo", "Uganda", "Zambia", "Zimbabwe",
}

loans = pd.read_csv(sys.argv[1])
africa = loans[loans["country"].isin(AFRICA)].drop(columns=["use"])
africa.to_csv("kiva_africa_loans.csv.gz", index=False, compression="gzip")
print(f"Kept {len(africa)} of {len(loans)} loans from {africa['country'].nunique()} African countries")

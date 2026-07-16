"""
Data feed - reads your XAU_15m_data.csv directly, no pandas needed.
File format: Date;Open;High;Low;Close;Volume
Date format: 2004.06.11 07:15

Filters by date range while reading, so the whole 26MB file
never needs to sit fully in memory - only the rows you actually want.
"""

import csv


class HistoricalCSVFeed:
    def __init__(self, csv_path: str):
        self.csv_path = csv_path

    def load_filtered(self, start_date: str, end_date: str):
        """
        start_date/end_date format: 'YYYY-MM-DD' (e.g. '2023-01-01', '2025-01-01')
        Returns list of dicts, oldest -> newest, matching what strategy.py expects.
        """
        prices = []

        with open(self.csv_path, "r") as f:
            reader = csv.reader(f, delimiter=";")
            next(reader)  # skip header row

            for row in reader:
                if len(row) < 5:
                    continue  # skip any blank/broken lines

                date_str = row[0]  # e.g. "2023.06.11 07:15"
                day_part = date_str.split(" ")[0].replace(".", "-")  # "2023-06-11"

                if day_part < start_date or day_part > end_date:
                    continue

                prices.append({
                    "date": date_str,
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                })

        prices.sort(key=lambda p: p["date"])
        return prices

# Persisted data

This directory is the default local root for persisted pipeline data. Generated
Parquet and metadata files are intentionally ignored by Git.

Set `AGENTIC_DATA_ROOT` or pass `root=` to `ParquetStorage` to store data
somewhere else.

## Layout

Market data uses interval-first partitioning with one file per symbol:

```text
raw/
  yfinance/
    1d/
      NVDA.parquet
      NVDA.metadata.json
      HMWO.L.parquet
      HMWO.L.metadata.json
```

Cash distributions are stored independently from prices so dividends and fund
distributions can be inspected and used explicitly in total-return calculations:

```text
raw/
  yfinance/
    distributions/
      NVDA.parquet
      NVDA.metadata.json
      VHYL.L.parquet
      VHYL.L.metadata.json
```

Each distribution row records `cash_amount` per share/unit plus `source`.
An empty distribution dataset is valid for an instrument with no recorded cash
payments.

Qualitative data uses dataset-first partitioning with one file per symbol:

```text
raw/
  finnhub/
    recommendations/
      NVDA.parquet
      NVDA.metadata.json
    insider_sentiment/
      NVDA.parquet
      NVDA.metadata.json
```

The same conventions can be used under other layers such as `processed/` and
`features/`.

Each Parquet file has a JSON sidecar containing the schema version, dataset
identity, row count, time range, update timestamp, and serialized DataFrame
attributes. The sidecar is the persistence contract for dataset metadata rather
than relying on Parquet-specific handling of `DataFrame.attrs`.

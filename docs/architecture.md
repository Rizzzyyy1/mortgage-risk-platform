# Architecture and evidence flow

```mermaid
flowchart TD
    V[Immutable vendor file and official schema] --> I[Schema validation and bulk ingestion]
    I --> Q[Key, count and balance reconciliation]
    Q --> E[Exposure eligibility and exclusions]
    E --> D[Monthly descriptive aggregates and event episodes]
    D --> B[Competing-event benchmark]
    D --> M[Chronological model design and evaluation]
    B --> S[Hypothetical stress and loss calculations]
    M --> R[Consolidated validation and monitoring replay]
    S --> R
    R --> H[Fingerprint checks for reporting inputs]
    H --> UI[Local aggregate dashboard and executive memo]
    X[Invented synthetic inputs] --> ENGINE[Shared competing-event and loss functions]
    ENGINE --> DEMO[Vendor-free JSON demo and checksums]
```

Python orchestrates and implements transparent calculations; DuckDB/SQL performs set-based aggregation; Parquet retains detailed analytical outputs. Raw data and accepted runs are immutable inputs. A new run gets a new directory. The dashboard presents bounded saved aggregates and does not fit models or load loan-level records.

The empirical model and illustrative loss engine are separate branches: the project does not claim the estimated 12-month model drives calibrated lifetime portfolio losses. Validation checks and reporting integrity must pass before a new dashboard is accepted.

The synthetic review path is self-contained. The historical path currently retains cohort-specific source and run references; generic orchestration, production scheduling and disaster recovery are not implemented.

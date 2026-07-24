# Data Sources — Status & Replacement Investigation

Tracks the registered data sources for `spark-match-data-pipeline` and
the parallel investigation into a replacement for the deprecated
Ponte en Carrera source.

## Registered sources

### `ponte_en_carrera` — DEPRECATED

| Field | Value |
|---|---|
| Status | **Deprecated as of 2026-07-12** |
| Upstream | https://ponteencarrera.minedu.gob.pe/pec-portal-web/inicio/donde-estudiar |
| Reason | MINEDU is decommissioning the portal. The "¿Dónde estudio?" endpoint returns HTTP 500. Confirmed by teammate report; portal team is sunsetting the platform. |
| Last known selectors | `<a class="opcion__button">` containing `<p class="opcion__button--text">¿Dónde estudio?</p>` (HTML restructured; old `id="btnBuscar"` no longer exists) |
| Historical data | `data/ponte_en_carrera/raw.xlsx` (committed to git) — usable by `data_clean.py` via `load()` |
| Source class | `src/sources/ponte_en_carrera.py` (marked `deprecated = True`, `fetch()` raises `SourceFetchError`) |
| DVC stage | `dvc.yaml` → `ingest` is `frozen: true`, skipped automatically by `dvc repro` |

**Workaround until a replacement is wired**: pipeline runs against the
git-tracked historical snapshot via:

```bash
uv run dvc repro clean features
```

**Diagnostic commands**:

```bash
uv run python -m src.ingestion --list              # empty (PEC is hidden as deprecated)
uv run python -m src.ingestion --list --all        # shows "(deprecated)" marker
uv run python -m src.ingestion --list-deprecated   # shows only PEC
uv run python -m src.ingestion ponte_en_carrera    # warns + raises SourceFetchError
```

---

## Replacement candidates under investigation

PEC provided a single comprehensive Excel with one row per
(career, institution) pair, covering: family/career name, institution,
location, type (instituto/universidad), management (public/private),
duration, annual cost, admission rate, monthly income, scholarships,
postulants/admitted counts. Finding a single replacement covering all
fields is unlikely; a multi-source aggregator is more realistic.

### 1. MINEDU Datos Abiertos — `datos.minedu.gob.pe` (NOT VERIFIED)

- **Status**: HTTP transport error when probed on 2026-07-12 — may be
  offline, redirected, or behind a CDN that blocks the probe. Needs
  browser verification.
- **What's likely there**: open data catalog (XLSX/CSV downloads)
  spanning multiple MINEDU programs: censo educativo, ESCALE,
  trayectoria docente, etc.
- **Pros**: Official source, comprehensive, free.
- **Cons**: Probably not a single dataset with career catalog; likely
  split across multiple files that need joining.

### 2. SUNEDU — `sunedu.gob.pe`

- **Status**: Verified live on 2026-07-12.
- **What's there**: `https://www.sunedu.gob.pe/lista-de-universidades-licenciadas/`
  lists accredited universities. A separate page exists for denied
  licenses. Two distinct static HTML pages.
- **Pros**: Authoritative list of *universities* (not institutos), with
  licensing status.
- **Cons**: No career catalog, no costs, no admission rates. Would
  complement other sources, not replace PEC alone.

### 3. MINEDU PIDE — `pide.minedu.gob.pe`

- **Status**: NOT investigated yet.
- **What's likely there**: Plataforma Integrada de Datos Educativos —
  indicators per institution/department.
- **Pros**: Could provide enrollment counts, geographic distribution.
- **Cons**: Aggregated indicators, not raw career catalog.

### 4. INEI — `inei.gob.pe`

- **Status**: NOT investigated yet.
- **What's likely there**: Census data, education statistics.
- **Pros**: National coverage, official.
- **Cons**: Annual snapshots, not real-time. Aggregated, not per-career.

### 5. datos.gob.pe — Peru Open Data Portal

- **Status**: NOT investigated yet.
- **What's likely there**: Catalog of public datasets from multiple
  ministries. May index MINEDU datasets.
- **Pros**: Centralized discovery.
- **Cons**: Discovery only; actual files live on each ministry's site.

### 6. PRONABEC — `pronabec.gob.pe`

- **Status**: NOT investigated yet.
- **What's likely there**: Scholarship program data (Beca 18, etc.),
  including lists of eligible institutions and careers.
- **Pros**: Already focused on education pathways; would integrate well
  with CareerMatch's user value prop.
- **Cons**: Scholarship-focused, not a general career catalog.

---

## Follow-up investigation plan

Ordered by expected ROI:

1. **[ ] Browser-verify `datos.minedu.gob.pe`** — confirm whether the
   transport error was a probe issue or a real outage. If up, browse
   the catalog for "Oferta Educativa Superior" or "Carreras"
   datasets. *(~10 min)*
2. **[ ] Search `datos.gob.pe` for "carreras" / "oferta educativa"** —
   may surface MINEDU or MEF datasets we missed. *(~5 min)*
3. **[ ] Check PRONABEC for an institution/career catalog API** —
   they often have structured data for their scholarship filters.
   *(~15 min)*
4. **[ ] Confirm with MINEDU team / teammate** whether PEC data is
   migrating somewhere internal or being discontinued outright. *(varies)*
5. **[ ] If a single replacement is not viable**, plan a multi-source
   aggregator:
   - `universities` (SUNEDU licensed list) → institution metadata
   - `careers` (MINEDU/PIDE/pronabec) → career catalog
   - `economics` (MINEDU datos abiertos or scraped) → costs, admission rates
   - Join via `(career_name, institution_name)` keys

---

## How to add a new source

When a replacement is identified:

1. Create `src/sources/<new_source>.py` implementing `DataSource`:
   - Set `name = "<new_source>"`
   - Implement `fetch()` → returns path to downloaded file
   - Implement `load(path)` → returns DataFrame (pure function)
   - Decorate with `@register`
2. Add `from .<new_source> import <NewSource>` to `src/sources/__init__.py`
3. Add a wiring branch in `src/ingestion.py:_build_source()` for the new
   class' constructor signature
4. Update `dvc.yaml` to add a stage for the new source (or add it to the
   existing `ingest` stage's list)
5. Add tests in `tests/sources/<new_source>.py`
6. Update this README to mark the new source as **Active** and remove
   the deprecation notice

The full pipeline (clean → features → DVC) requires no changes when a
new source is added.
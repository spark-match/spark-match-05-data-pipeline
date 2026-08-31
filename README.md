# spark-match-05-data-pipeline

Pipeline de datos de **Spark Match**: desde el catálogo oficial de Ponte en
Carrera (MINEDU) hasta el dataset que consume el motor de recomendación del
agente (`spark-match-07-deep-agent`).

Las etapas están declaradas en `dvc.yaml` y se reproducen con
`uv run dvc repro`.

> ### ⚠️ La ingesta está congelada
>
> MINEDU retiró el portal `ponteencarrera.minedu.gob.pe` en julio de 2026 y el
> upstream devuelve HTTP 500. La etapa `ingest` está marcada `frozen: true` en
> DVC y `PonteEnCarreraSource.fetch()` lanza `SourceFetchError`.
>
> Las etapas siguientes se reproducen contra el `raw.xlsx` histórico versionado
> en git:
>
> ```bash
> uv run dvc repro clean features riasec
> ```
>
> Actualizar el catálogo requiere una fuente nueva. Ver `src/sources/README.md`.

## Flujo de procesamiento

### 1. ingestion.py — congelada

Descargaba la base desde el portal Ponte en Carrera con Selenium.

Funciones principales:

* Acceso automático al portal.
* Ejecución de la búsqueda de carreras y universidades.
* Descarga del archivo Excel oficial.
* Actualización del dataset principal (`data/raw.xlsx`).
* Creación de snapshots históricos en la carpeta `snapshots/`.

Objetivo:

Mantener una copia reproducible de los datos utilizados por cada versión del sistema.

---

### 2. data_clean.py

Realiza la limpieza y estandarización inicial de los datos descargados.

Procesos principales:

* Lectura del archivo Excel original.
* Renombrado de columnas a formato estandarizado (`snake_case`).
* Eliminación de registros incompletos.
* Conversión de variables numéricas a tipos adecuados.
* Exportación del dataset limpio a `data/filtered.csv`.

Objetivo:

Generar una versión consistente y estructurada de los datos para etapas posteriores.

---

### 3. feature_engineering.py

Construye las variables utilizadas por el motor de recomendación.

Procesos principales:

#### Detección de valores problemáticos

Identificación de registros con:

* duración inválida
* ingresos faltantes
* costos faltantes
* tasas de admisión faltantes o fuera de rango

#### Creación de flags de imputación

Para cada variable crítica se genera un indicador que permite rastrear qué registros fueron imputados.

Ejemplos:

* duration_imputed_flag
* monthly_income_imputed_flag
* annual_cost_imputed_flag
* admission_rate_imputed_flag

#### Imputación jerárquica

Las variables faltantes se completan siguiendo el siguiente orden:

1. Mediana por familia de carrera e institución.
2. Mediana por familia de carrera.
3. Valor fallback configurado.

#### Generación de variables normalizadas

Se crean variables normalizadas entre 0 y 1:

* income_norm
* admission_norm
* cost_norm
* duration_norm

Las variables donde un valor menor es preferible (costo y duración) se invierten para que un score más alto siempre represente una mejor alternativa.

#### Versionado de configuración

Las reglas de imputación se almacenan en:

`data/feature_config.json`

permitiendo reproducibilidad y trazabilidad de experimentos.

#### Snapshots

En cada ejecución se generan:

* Snapshot del dataset de features.
* Snapshot de la configuración utilizada.

Objetivo:

Construir un dataset reproducible y preparado para el motor de scoring.

---

### 4. riasec_tagging.py

Asigna un perfil RIASEC de tres letras a cada carrera única del dataset,
usando un LLM en AWS Bedrock — el mismo cliente `ChatBedrock` que usa el
agente, para compartir una sola ruta de autenticación y un solo formato de
id de modelo.

Cada fila queda marcada con su procedencia en la columna `riasec_source`, de
modo que una etiqueta generada por el modelo nunca se confunde con una
validada a mano. Las carreras que el modelo no logra resolver se marcan como
pendientes en lugar de recibir una etiqueta inventada.

Salida: `data/riasec_tags.csv` (554 carreras etiquetadas).

Objetivo:

Dar al motor de scoring el eje de afinidad vocacional, que es el criterio de
mayor peso del ranking.

---

## Artefactos generados

### Datos

* data/raw.xlsx — descarga original (histórica; la ingesta está congelada)
* data/filtered.csv — limpio y estandarizado
* data/features.csv — 6.208 filas carrera × institución, con features normalizadas
* data/riasec_tags.csv — 554 carreras con perfil RIASEC

### Configuración

* data/feature_config.json

### Snapshots

* snapshots/raw_YYYYMMDD_HHMMSS.xlsx
* snapshots/features/features_YYYYMMDD_HHMMSS.csv
* snapshots/configs/feature_config_YYYYMMDD_HHMMSS.json

---

## Consideraciones

* Los ingresos corresponden a información reportada por Ponte en Carrera.
* El portal de origen ya no está disponible: los datos son una foto histórica, no una fuente viva.
* Las imputaciones se encuentran identificadas mediante flags para facilitar auditoría y monitoreo.
* Los snapshots permiten reproducir exactamente los resultados obtenidos por una versión específica del sistema.

## Quién consume esto

El agente (`spark-match-07-deep-agent`) lleva el catálogo dentro de su imagen y
lo puntúa con `src/tools/recommendation/scoring.py`, que pondera cuatro
criterios: afinidad RIASEC (0.50), ingreso (0.20), accesibilidad de admisión
(0.20) y costo (0.10). La duración se calcula aquí pero **no** entra en el
ranking.

El scoring normaliza contra percentiles 5 y 95 del dataset, usando solo las
filas con medición real — por eso las banderas `*_imputed_flag` que produce
este pipeline importan: permiten excluir las medianas de familia, que
comprimen la distribución.


# data_pipeline

Este módulo contiene todo el flujo de datos de CareerMatch Perú, desde la descarga de la información oficial de Ponte en Carrera hasta la generación de variables listas para el motor de recomendación.

## Flujo de procesamiento

### 1. ingestion.py

Obtiene automáticamente la base de datos desde el portal Ponte en Carrera utilizando Selenium.

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

Construir un dataset reproducible y preparado para el motor de scoring de CareerMatch.

---

## Artefactos generados

### Datos

* data/raw.xlsx
* data/filtered.csv
* data/features.csv

### Configuración

* data/feature_config.json

### Snapshots

* snapshots/raw_YYYYMMDD_HHMMSS.xlsx
* snapshots/features/features_YYYYMMDD_HHMMSS.csv
* snapshots/configs/feature_config_YYYYMMDD_HHMMSS.json

---

## Consideraciones

* Los ingresos corresponden a información reportada por Ponte en Carrera.
* Los indicadores pueden actualizarse cuando el portal publique nuevas versiones.
* Las imputaciones se encuentran identificadas mediante flags para facilitar auditoría y monitoreo.
* Los snapshots permiten reproducir exactamente los resultados obtenidos por una versión específica del sistema.

Este pipeline constituye la base de datos versionada utilizada por el motor de recomendación de CareerMatch Perú.


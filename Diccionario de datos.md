# Diccionario de datos

## Clasificación de variables según su uso en el sistema

Con el objetivo de diferenciar el propósito funcional de cada variable dentro del sistema, las variables de `features.csv` se clasifican en las siguientes categorías. Esta clasificación se presenta en la columna **"Uso en el sistema"** del diccionario de datos de la siguiente sección y permite distinguir aquellas empleadas en la **fórmula de scoring** de las utilizadas para **consultas**, **generación de explicaciones** y **auditoría de calidad de datos**.

### Fórmula de scoring

Corresponde exclusivamente a las variables normalizadas que son utilizadas como entrada de la fórmula de scoring. Estas variables se encuentran en una escala común **[0,1]**, permitiendo combinar criterios originalmente medidos en diferentes unidades (soles, años y porcentajes).

Estas variables **no deben utilizarse para explicar el resultado al usuario**, ya que representan transformaciones matemáticas sin interpretación directa. Por ejemplo, no tendría sentido indicar que una carrera fue recomendada porque obtuvo un `cost_norm = 0.82`; en su lugar, la explicación debe utilizar la variable imputada correspondiente (`annual_cost_imputed`), expresando el costo en soles.

La relación entre cada variable utilizada por la fórmula de scoring y la variable utilizada para consultas y explicación de resultados es la siguiente:

| Variable Normalizada | Variable para consultas y explicación | Interpretación |
|---------------------|---------------------------------------|----------------|
| `income_norm` | `monthly_income_imputed` | Ingreso mensual promedio de los egresados (S/). |
| `cost_norm` | `annual_cost_imputed` | Costo anual de estudiar la carrera (S/). |
| `duration_norm` | `duration_years_imputed` | Duración de la carrera (años). |
| `admission_norm` | `admission_rate_imputed` | Porcentaje de ingresantes respecto a postulantes (%). |

Variables pertenecientes a esta categoría:

- `income_norm`
- `cost_norm`
- `duration_norm`
- `admission_norm`

---

### Consultas y explicación de resultados

Corresponde a las variables utilizadas para realizar consultas, filtros, recuperar registros y generar explicaciones comprensibles para el usuario final.

En el caso de las variables numéricas, se emplean siempre las versiones **imputadas**, ya que representan los valores finales utilizados por el sistema después del proceso de tratamiento de datos faltantes o inválidos.

Variables pertenecientes a esta categoría:

- `id`
- `career_family`
- `career`
- `institution`
- `location`
- `institution_type`
- `management_type`
- `duration_years_imputed`
- `monthly_income_imputed`
- `annual_cost_imputed`
- `admission_rate_imputed`

---

### Auditoría de calidad de datos

Corresponde a variables auxiliares cuyo propósito es registrar si un determinado atributo requirió imputación durante el proceso de ingeniería de características.

Estas variables facilitan la trazabilidad del pipeline y permiten identificar registros cuyo valor final fue estimado en lugar de provenir directamente de la fuente de datos.

Variables pertenecientes a esta categoría:

- `duration_imputed_flag`
- `monthly_income_imputed_flag`
- `annual_cost_imputed_flag`
- `admission_rate_imputed_flag`

---

### No utilizadas directamente

Corresponde a variables originales provenientes del portal Ponte en Carrera que son conservadas en el conjunto de datos, pero que no participan directamente en el cálculo del score ni en la generación de explicaciones al usuario.

En el caso de las variables numéricas (`duration_years`, `annual_cost`, `monthly_income` y `admission_rate`), estas permanecen únicamente como referencia, ya que el sistema utiliza sus versiones imputadas.

Variables pertenecientes a esta categoría:

- `duration_years`
- `annual_cost`
- `monthly_income`
- `admission_rate`
- `scholarships`
- `admitted`
- `applicants`
- `enrolled`

## Diccionario de datos

| Variable | Esquema | Descripción | Transformación | Uso en el sistema |
|----------|---------|-------------|----------------|-------------------|
| **id** | Integer | Identificador único del registro correspondiente a una combinación Carrera–Institución. | Sin transformación. Se conserva el identificador original del portal Ponte en Carrera. | Consultas y explicación de resultados |
| **career_family** | String (81 categorías) | Familia o área de conocimiento a la que pertenece la carrera (por ejemplo, Ingeniería Civil, Enfermería o Contabilidad y Finanzas). | Sin transformación. Se conserva el valor original. | Consultas y explicación de resultados |
| **career** | String (554 categorías) | Nombre de la carrera profesional ofertada por la institución educativa. | Sin transformación. Se conserva el valor original. | Consultas y explicación de resultados |
| **institution** | String (1071 categorías) | Nombre de la universidad o instituto que oferta la carrera. | Sin transformación. Se conserva el valor original. | Consultas y explicación de resultados |
| **location** | String (25 categorías) | Departamento del Perú donde se ubica la institución educativa. | Sin transformación. Se conserva el valor original. | Consultas y explicación de resultados |
| **institution_type** | String (2 categorías: Universidad, Instituto) | Tipo de institución educativa. | Sin transformación. Se conserva el valor original. | Consultas y explicación de resultados |
| **management_type** | String (2 categorías: Pública, Privada) | Tipo de gestión de la institución educativa. | Sin transformación. Se conserva el valor original. | Consultas y explicación de resultados |
| **duration_years** | Float | Duración original de la carrera en años reportada por Ponte en Carrera. | Conversión a tipo numérico. Los valores menores o iguales a 0, mayores a 10 o nulos son identificados posteriormente para imputación. | No utilizada directamente |
| **annual_cost** | Float | Costo anual de estudiar la carrera, expresado en soles. | Conversión a tipo numérico. Los valores menores o iguales a 0 o nulos son identificados posteriormente para imputación. | No utilizada directamente |
| **admission_rate** | Float | Porcentaje de ingresantes respecto al total de postulantes. | Conversión a tipo numérico. Posteriormente los valores mayores a 90%, menores o iguales a 0 o nulos son tratados mediante imputación. | No utilizada directamente |
| **monthly_income** | Float | Ingreso mensual promedio de los egresados, expresado en soles. | Conversión a tipo numérico. Los valores menores o iguales a 0 o nulos son identificados posteriormente para imputación. | No utilizada directamente |
| **scholarships** | String (2 categorías: Sí, No) | Indica si existen becas educativas asociadas a la carrera o institución. | Sin transformación. Se conserva el valor original. | No utilizada directamente |
| **admitted** | Float | Número de ingresantes registrados para la carrera e institución. | Conversión a tipo numérico. | No utilizada directamente |
| **applicants** | Float | Número de postulantes registrados para la carrera e institución. | Conversión a tipo numérico. | No utilizada directamente |
| **enrolled** | Float | Número de estudiantes matriculados en la carrera e institución. | Conversión a tipo numérico. | No utilizada directamente |
| **duration_imputed_flag** | Boolean | Indica si la duración original requirió imputación. | Toma el valor **True** cuando `duration_years` es menor o igual a 0, mayor a 10 o nulo; en caso contrario toma **False**. | Auditoría de calidad de datos |
| **monthly_income_imputed_flag** | Boolean | Indica si el ingreso mensual requirió imputación. | Toma el valor **True** cuando `monthly_income` es menor o igual a 0 o nulo; en caso contrario toma **False**. | Auditoría de calidad de datos |
| **annual_cost_imputed_flag** | Boolean | Indica si el costo anual requirió imputación. | Toma el valor **True** cuando `annual_cost` es menor o igual a 0 o nulo; en caso contrario toma **False**. | Auditoría de calidad de datos |
| **admission_rate_imputed_flag** | Boolean | Indica si la tasa de admisión requirió imputación. | Toma el valor **True** cuando `admission_rate` es menor o igual a 0, mayor a 90 o nulo; en caso contrario toma **False**. | Auditoría de calidad de datos |
| **duration_years_imputed** | Float | Duración definitiva de la carrera utilizada por el sistema para consultas, filtros y generación de recomendaciones. | La imputación sigue una estrategia jerárquica: **(1)** mediana por combinación *(career_family, institution_type)*; **(2)** si no existe información suficiente, mediana de *career_family*; **(3)** si aún no puede imputarse, se utiliza un valor de respaldo de **4 años para Institutos** y **5 años para Universidades**. | Consultas y explicación de resultados |
| **monthly_income_imputed** | Float | Ingreso mensual promedio definitivo de los egresados utilizado por el sistema para consultas, filtros y generación de recomendaciones. | La imputación sigue una estrategia jerárquica: **(1)** mediana por combinación *(career_family, institution_type)*; **(2)** mediana por *career_family*; **(3)** valor de respaldo de **S/ 1100**. | Consultas y explicación de resultados |
| **annual_cost_imputed** | Float | Costo anual definitivo utilizado por el sistema para consultas, filtros y generación de recomendaciones. | La imputación sigue una estrategia jerárquica: **(1)** mediana por combinación *(career_family, institution_type)*; **(2)** mediana por *career_family*; **(3)** valor de respaldo de **S/ 0**. | Consultas y explicación de resultados |
| **admission_rate_imputed** | Float | Tasa de admisión definitiva utilizada por el sistema para consultas, filtros y generación de recomendaciones. | Primero el valor se restringe al intervalo **[0, 90]** mediante *clipping*. Posteriormente la imputación sigue la estrategia jerárquica: **(1)** mediana por *(career_family, institution_type)*; **(2)** mediana por *career_family*; **(3)** valor de respaldo de **0%**. | Consultas y explicación de resultados |
| **income_norm** | Float (0–1) | Puntaje normalizado que representa el atractivo del ingreso mensual esperado. Valores más altos representan mayores ingresos. | Se aplica primero la transformación **log1p()** sobre `monthly_income_imputed` y posteriormente una normalización **Min-Max** al intervalo **[0,1]**. | **Fórmula de scoring** |
| **admission_norm** | Float (0–1) | Puntaje normalizado asociado a la facilidad de ingreso. Valores más altos representan mayores tasas de admisión. | Se aplica una normalización **Min-Max** sobre `admission_rate_imputed`. | **Fórmula de scoring** |
| **cost_norm** | Float (0–1) | Puntaje normalizado de accesibilidad económica. Valores altos representan carreras con menor costo. | Se aplica primero **log1p()** sobre `annual_cost_imputed`, luego una normalización **Min-Max** y finalmente la inversión del indicador mediante **1 − score**, de modo que menores costos produzcan puntajes más altos. | **Fórmula de scoring** |
| **duration_norm** | Float (0–1) | Puntaje normalizado asociado a la duración de la carrera. Valores altos representan carreras de menor duración. | Se aplica una normalización **Min-Max** sobre `duration_years_imputed` y posteriormente se invierte el indicador mediante **1 − score**, de modo que carreras más cortas obtengan mayores puntajes. | **Fórmula de scoring** |

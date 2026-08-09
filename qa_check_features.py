# -*- coding: utf-8 -*-
"""
QA - Verificacion de features.csv (Fabiola / integracion)
=========================================================
Chequea el dataset que consume el motor de scoring y el etiquetado RIASEC.
Valida puntos del plan de pruebas (QA_TEST_PLAN.md):
  - INT-002: la columna de region usa "Lima" (NO "Lima Metropolitana")
  - Normalizacion (INT-011 lado datos): las columnas *_norm estan en [0, 1]
  - Columnas esperadas presentes; conteos (filas, carreras, regiones)

Uso:  python qa_check_features.py
      (correr desde la carpeta del repo spark-match-05-data-pipeline)
"""

from pathlib import Path
import sys
import pandas as pd

FEATURES = Path(__file__).resolve().parent / "data" / "features.csv"

# Columnas que el resto del sistema espera
REQUIRED_COLS = ["career", "career_family", "location"]
NORM_COLS = ["income_norm", "admission_norm", "cost_norm", "duration_norm"]

# Conteos esperados (segun el informe: 6208 filas, 554 carreras, 25 dptos)
EXPECTED_ROWS = 6208
EXPECTED_CAREERS = 554
EXPECTED_REGIONS = 25

OK = "[ OK ]"
FAIL = "[FALLA]"
WARN = "[AVISO]"


def main() -> int:
    print("=" * 60)
    print("QA - features.csv")
    print("=" * 60)

    if not FEATURES.exists():
        print(f"{FAIL} No se encontro el archivo: {FEATURES}")
        return 1

    # utf-8-sig para quitar el BOM del inicio
    df = pd.read_csv(FEATURES, encoding="utf-8-sig")
    fails = 0

    # 1) Columnas esperadas
    print("\n1) Columnas esperadas")
    for col in REQUIRED_COLS + NORM_COLS:
        if col in df.columns:
            print(f"   {OK} existe '{col}'")
        else:
            print(f"   {FAIL} FALTA la columna '{col}'")
            fails += 1

    # 2) INT-002: regiones
    print("\n2) Regiones (INT-002)")
    if "location" in df.columns:
        regiones = sorted(df["location"].dropna().astype(str).unique())
        malas = [r for r in regiones if "metropolitana" in r.lower()]
        if malas:
            print(f"   {FAIL} Hay regiones con 'Metropolitana': {malas}")
            fails += 1
        else:
            print(f"   {OK} Ninguna region dice 'Metropolitana'")
        print(f"   -> {len(regiones)} regiones unicas "
              f"({'OK' if len(regiones) == EXPECTED_REGIONS else 'esperaba ' + str(EXPECTED_REGIONS)})")
        print(f"   -> ejemplos: {', '.join(regiones[:6])} ...")
    else:
        print(f"   {WARN} no hay columna 'location', se omite")

    # 3) Normalizacion en [0,1] (INT-011 lado datos)
    print("\n3) Columnas normalizadas en [0, 1]")
    tol = 1e-9
    for col in NORM_COLS:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce")
        lo, hi = s.min(), s.max()
        n_nan = int(s.isna().sum())
        dentro = (lo >= -tol) and (hi <= 1 + tol)
        marca = OK if dentro else FAIL
        if not dentro:
            fails += 1
        extra = f"  (NaN: {n_nan})" if n_nan else ""
        print(f"   {marca} {col:16s} min={lo:.4f}  max={hi:.4f}{extra}")

    # 4) Conteos
    print("\n4) Conteos")
    def chk(nombre, real, esperado):
        marca = OK if real == esperado else WARN
        print(f"   {marca} {nombre}: {real} (esperado {esperado})")
    chk("Filas", len(df), EXPECTED_ROWS)
    if "career" in df.columns:
        chk("Carreras unicas", df["career"].nunique(), EXPECTED_CAREERS)

    # 5) Nota sobre afinidad (INT-005 / INT-011)
    print("\n5) Nota")
    print("   La AFINIDAD/RIASEC no es columna del dataset: la deriva el agente")
    print("   en la conversacion. Su normalizacion a [0,1] se valida en el")
    print("   repo del agente (matching.py, INT-011 - PR #19).")

    # Resumen
    print("\n" + "=" * 60)
    if fails == 0:
        print(f"{OK} TODO OK - {len(df)} filas verificadas, sin fallas.")
    else:
        print(f"{FAIL} {fails} verificacion(es) con problema. Revisar arriba.")
    print("=" * 60)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

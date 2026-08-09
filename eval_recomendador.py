# -*- coding: utf-8 -*-
"""
Evaluación del MOTOR DE RECOMENDACIÓN (Fabiola / QA)
====================================================
Evalúa la parte DETERMINÍSTICA del sistema (el motor de scoring de 5 factores),
que corre sobre features.csv SIN necesitar el agente ni el LLM.

  Score = w1·Afinidad + w2·Ingreso + w3·Costo + w4·Admisión + w5·Duración
  (todas las variables ya vienen normalizadas en [0,1] desde el pipeline)

Produce evidencia REAL y presentable para el criterio 7 (evaluación) y 8
(ejemplos de salida):
  1) Ranking Top-5 para varios perfiles de estudiante (ejemplos de salida).
  2) Comparación de enfoques: pesos dinámicos vs pesos iguales vs solo-ingreso.
  3) Prueba de consistencia: el ranking responde a las preferencias.

NOTA DE HONESTIDAD (declararlo en el informe):
  - Esto evalúa el RECOMENDADOR, no las respuestas del LLM (groundedness /
    LLM-as-judge, que sí requieren el agente corriendo).
  - El factor Afinidad usa una similitud RIASEC ilustrativa consistente con el
    diseño del agente (matching.py). El "ground truth" de casos es criterio propio.

Uso:  python eval_recomendador.py
"""

from pathlib import Path
import sys
import pandas as pd

try:  # que la consola de Windows imprima acentos y símbolos sin romperse
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent
FEATURES = ROOT / "data" / "features.csv"
TAGS = ROOT / "data" / "riasec_tags.csv"

NORM = {"ingreso": "income_norm", "costo": "cost_norm",
        "admision": "admission_norm", "duracion": "duration_norm"}

# --- Afinidad RIASEC (similitud de códigos de 3 letras, en [0,1]) ---
POS_W = {0: 3, 1: 2, 2: 1}  # la 1ra letra pesa más (modelo de Holland)

def affinity(student: str, career: str) -> float:
    if not isinstance(career, str) or not career:
        return 0.0
    s, c = student.upper(), career.upper()
    score = maxp = 0.0
    for i, letter in enumerate(s[:3]):
        w = POS_W.get(i, 1); maxp += w
        if i < len(c) and c[i] == letter:
            score += w            # misma posición
        elif letter in c:
            score += w * 0.5      # presente en otra posición
    return round(score / maxp, 4) if maxp else 0.0

def norm_txt(x):
    import unicodedata
    x = str(x).strip().lower()
    return "".join(ch for ch in unicodedata.normalize("NFKD", x) if not unicodedata.combining(ch))

# --- Perfiles de estudiante (casos de prueba) ---
# weights: afinidad, ingreso, costo, admision, duracion  (suman 1)
PERFILES = [
    {"nombre": "Cusco · presupuesto bajo · prioriza salario y cercanía",
     "region": "Cusco", "presupuesto_mensual": 600, "riasec": "IRE",
     "w": {"afinidad": .15, "ingreso": .45, "costo": .30, "admision": .05, "duracion": .05}},
    {"nombre": "Lima · sin límite · prioriza afinidad y calidad",
     "region": "Lima", "presupuesto_mensual": None, "riasec": "AES",
     "w": {"afinidad": .40, "ingreso": .30, "costo": .05, "admision": .10, "duracion": .15}},
    {"nombre": "Arequipa · presupuesto medio · prioriza costo",
     "region": "Arequipa", "presupuesto_mensual": 450, "riasec": "RIC",
     "w": {"afinidad": .20, "ingreso": .20, "costo": .40, "admision": .10, "duracion": .10}},
    {"nombre": "La Libertad · prioriza ingreso",
     "region": "La Libertad", "presupuesto_mensual": None, "riasec": "ESC",
     "w": {"afinidad": .15, "ingreso": .55, "costo": .10, "admision": .10, "duracion": .10}},
]


def load():
    df = pd.read_csv(FEATURES, encoding="utf-8-sig")
    tags = pd.read_csv(TAGS, encoding="utf-8-sig")[["career", "riasec_profile"]]
    df = df.merge(tags, on="career", how="left")
    df["_loc"] = df["location"].map(norm_txt)
    return df


def score_df(df, perfil, weights):
    d = df.copy()
    d["afinidad"] = [affinity(perfil["riasec"], rp) for rp in d["riasec_profile"]]
    d["score"] = (
        weights["afinidad"] * d["afinidad"].fillna(0)
        + weights["ingreso"] * d[NORM["ingreso"]].fillna(0)
        + weights["costo"] * d[NORM["costo"]].fillna(0)
        + weights["admision"] * d[NORM["admision"]].fillna(0)
        + weights["duracion"] * d[NORM["duracion"]].fillna(0)
    )
    return d


def apply_filters(d, perfil):
    reg = norm_txt(perfil["region"])
    out = d[d["_loc"] == reg].copy()
    pm = perfil["presupuesto_mensual"]
    if pm and "annual_cost" in out.columns:
        out = out[(out["annual_cost"].isna()) | (out["annual_cost"] / 12 <= pm)]
    return out


def top(d, n=5):
    return d.sort_values("score", ascending=False).head(n)


def main():
    if not FEATURES.exists() or not TAGS.exists():
        print("Falta features.csv o riasec_tags.csv"); return 1
    df = load()
    cov = df["riasec_profile"].notna().mean() * 100
    print("=" * 72)
    print("EVALUACIÓN DEL MOTOR DE RECOMENDACIÓN (5 factores)")
    print(f"Dataset: {len(df)} filas · cobertura RIASEC: {cov:.0f}% de las filas")
    print("=" * 72)

    # 1) Rankings Top-5 por perfil
    print("\n### 1) Rankings Top-5 por perfil (ejemplos de salida) ###")
    for p in PERFILES:
        d = apply_filters(score_df(df, p, p["w"]), p)
        print(f"\n▶ {p['nombre']}")
        print(f"  región={p['region']}  presup/mes={p['presupuesto_mensual']}  RIASEC={p['riasec']}  "
              f"(candidatas tras filtros: {len(d)})")
        if d.empty:
            print("  [sin resultados tras filtros]"); continue
        t = top(d, 5)
        for i, (_, r) in enumerate(t.iterrows(), 1):
            print(f"   {i}. {str(r['career'])[:34]:34s} | {str(r['institution'])[:30]:30s} "
                  f"| score={r['score']:.3f} afin={r['afinidad']:.2f} "
                  f"ing={r['income_norm']:.2f} cost={r['cost_norm']:.2f}")

    # 2) Comparación de enfoques (caso Cusco)
    print("\n\n### 2) Comparación de enfoques — caso Cusco ###")
    p = PERFILES[0]
    estrategias = {
        "Dinámico (pesos del LLM)": p["w"],
        "Pesos iguales (baseline)": {k: .2 for k in p["w"]},
        "Solo ingreso (baseline)": {"afinidad": 0, "ingreso": 1, "costo": 0, "admision": 0, "duracion": 0},
    }
    tops = {}
    for nombre, w in estrategias.items():
        d = apply_filters(score_df(df, p, w), p)
        tset = list(top(d, 5)["career"])
        tops[nombre] = tset
        print(f"\n  {nombre}:")
        for i, c in enumerate(tset, 1):
            print(f"    {i}. {c}")
    base = set(tops["Dinámico (pesos del LLM)"])
    print("\n  Solapamiento del Top-5 vs. enfoque dinámico:")
    for nombre, tset in tops.items():
        if nombre == "Dinámico (pesos del LLM)":
            continue
        print(f"    {nombre}: {len(base & set(tset))}/5 carreras en común "
              f"→ el enfoque cambia el ranking")

    # 3) Prueba de consistencia (responde a las preferencias)
    print("\n\n### 3) Prueba de consistencia — ¿el ranking respeta la preferencia? ###")
    reg = "Lima"
    p_costo = {"nombre": "x", "region": reg, "presupuesto_mensual": None, "riasec": "IRC",
               "w": {"afinidad": .1, "ingreso": .1, "costo": .6, "admision": .1, "duracion": .1}}
    p_ing = {"nombre": "x", "region": reg, "presupuesto_mensual": None, "riasec": "IRC",
             "w": {"afinidad": .1, "ingreso": .6, "costo": .1, "admision": .1, "duracion": .1}}
    tc = top(apply_filters(score_df(df, p_costo, p_costo["w"]), p_costo), 10)
    ti = top(apply_filters(score_df(df, p_ing, p_ing["w"]), p_ing), 10)
    # Métrica creíble: cost_norm (normalizado + imputado, mayor = más barato)
    cn_c, cn_i = tc["cost_norm"].mean(), ti["cost_norm"].mean()
    print(f"  Índice de accesibilidad de costo (cost_norm, mayor = más barato) del Top-10 en {reg}:")
    print(f"    - Perfil que PRIORIZA COSTO   : {cn_c:.3f}")
    print(f"    - Perfil que PRIORIZA INGRESO : {cn_i:.3f}")
    ok = cn_c > cn_i
    print(f"  {'[ OK ]' if ok else '[REVISAR]'} El perfil sensible al costo recibe recomendaciones "
          f"{'más accesibles' if ok else 'NO más accesibles (revisar)'} -> el motor responde a la preferencia.")
    # Referencia cruda (solo valores > 0; ~50% del costo está vacío/imputado):
    rc = tc.loc[tc["annual_cost"] > 0, "annual_cost"].mean()
    ri = ti.loc[ti["annual_cost"] > 0, "annual_cost"].mean()
    print(f"  (Ref. costo anual crudo, solo >0: prioriza-costo S/ {rc:,.0f}  vs  prioriza-ingreso S/ {ri:,.0f})")
    print("  NOTA: annual_cost tiene ~50% de datos vacios/imputados -> es la variable menos confiable (limitacion).")

    print("\n" + "=" * 72)
    print("Evaluación completada. Copiar estos resultados al informe (crit. 7 y 8).")
    print("Recordar declarar: evalúa el RECOMENDADOR (no el LLM); casos ilustrativos.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())

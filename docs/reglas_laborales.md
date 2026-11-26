# Reglas laborales

> **Todos los valores están POR VERIFICAR.** Confirmar vigencia y fuente antes de usarlos en lógica de cálculo.

Las reglas no se escriben en el código. Viven en la tabla `labor_rules`, por tenant y por régimen, con vigencia por fecha (`valid_from`, `valid_to`). Una regla del tenant prevalece sobre la global; dentro de cada nivel aplica la de vigencia más reciente que cubra la fecha.

Valores de referencia cargados en [`fixtures/labor_rules.json`](../fixtures/labor_rules.json):

| Regla | Régimen | Valor | Vigencia | Fuente | Estado |
|---|---|---|---|---|---|
| Jornada máxima semanal | private | 42 h | desde 15-jul-2026 | CST, Ley 2101 | por verificar |
| Divisor hora ordinaria mensual | private | 210 h (antes 220) | desde 15-jul-2026 | CST, Ley 2101 | por verificar |
| Jornada diurna / nocturna | private | 6:00–19:00 / 19:00–6:00 | | Ley 2466 | por verificar |
| Recargo nocturno | private | 35% | | CST | por verificar |
| Recargo dominical y festivo | private | 90% / 100% | desde 1-jul-2026 / 1-jul-2027 | Ley 2466 | por verificar |
| Jornada sector público (ESE) | public_ese | — | | Decreto 1042/1978 | por validar |
| Doble vinculación pública asistencial | public_dual | 12 h diarias, 66 h semanales | | Ley 269/1996 | por verificar |
| Contratistas (OPS) | contractor | sin jornada laboral | | | cuidar riesgo de contrato realidad |

Las fechas de inicio de vigencia de algunas filas del fixture son provisionales y deben confirmarse.

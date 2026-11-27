# Modelo de dominio (base)

| Entidad | Atributos principales | Notas |
|---|---|---|
| Tenant (clínica) | id, nombre | Un schema de PostgreSQL por tenant |
| Sede | id, tenant, nombre | |
| Servicio | id, sede, nombre | Urgencias, UCI, hospitalización, cirugía |
| Empleado | id, cargo, tipo de vinculación, horas contratadas, régimen, competencias | Un solo calendario por persona aunque trabaje en varias sedes o servicios |
| Tipo de turno | código (M, T, N, MT…), hora inicio/fin, horas, cruza medianoche | |
| Requerimiento de cobertura | servicio × día × franja × cargo × mínimo | |
| Preferencia | tipo (disponibilidad / suave / petición), peso, vigencia, origen (empleado, aprendida) | |
| Novedad | tipo (vacaciones, incapacidad, licencia, permiso), rango de fechas | |
| Cuadro (versión) | periodo, servicio, estado (borrador, publicado, ajustado) | Contiene asignaciones |
| Asignación | cuadro, empleado, día, turno, servicio | Debe poder explicar "¿por qué me tocó esto?" |
| Intercambio | solicitante, receptor, estado, aprobador | |
| Regla laboral | tenant (opcional), régimen, clave, valor, unidad, vigencia, fuente, estado de verificación | Ver [reglas_laborales.md](reglas_laborales.md) |

## Regímenes de vinculación

- `private`: Código Sustantivo del Trabajo.
- `public_ese`: sector público (ESE), régimen distinto; jornada por validar.
- `public_dual`: doble vinculación pública asistencial.
- `contractor`: contratistas (OPS). No tienen jornada laboral; se tratan aparte.

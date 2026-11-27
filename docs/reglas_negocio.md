# Reglas de negocio

## Principios

1. **El coordinador siempre aprueba.** LUNA propone 2–3 cuadros válidos; nunca publica sola.
2. **Toda regla es configurable por tenant.** La ley es el piso, no el único límite (descanso mínimo, máximo de noches seguidas, fines de semana libres al mes).
3. **Competencias obligatorias.** Solo se asigna a un servicio a quien esté habilitado para él (ej. UCI).
4. **Un calendario por persona.** Sin cruces entre sedes o servicios.
5. **Consentimiento para WhatsApp** (Ley 1581) antes de enviar cualquier mensaje.
6. **Explicabilidad.** Cada asignación debe responder "¿por qué me tocó esto?".
7. **El modelo de lenguaje solo interpreta mensajes.** El motor decide las asignaciones.

## Motor de asignación

| Tipo | Ejemplos | Implementación |
|---|---|---|
| Restricción dura | Cobertura mínima, competencia, un turno por día, novedades, horas máximas, descanso entre turnos | Constraint en CP-SAT |
| Casi dura | Disponibilidad fija del empleado ("no puedo martes tarde") | Constraint, con opción de relajar y alertar |
| Blanda | Preferencias con peso, peticiones puntuales, equidad histórica | Término ponderado en la función objetivo |

## Equidad

- Quien tuvo menos preferencias cumplidas tiene prioridad el mes siguiente.
- Se acumulan noches, festivos y fines de semana por persona en el tiempo.
- Cada cuadro muestra el % de preferencias cumplidas y a quién no se le cumplió.

## Datos

- Nunca usar datos reales de personas en código, pruebas, logs, ejemplos ni documentos.
- Base de datos del cliente: solo lectura por defecto.

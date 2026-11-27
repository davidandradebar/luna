# Guion de la demo (10 minutos)

Demo con una clínica ficticia ("Clínica Demo") de salud mental: hospitalización de agudos e intermedios, 25 personas (auxiliares de enfermería, enfermeras jefe, psiquiatras, psicólogos y terapeuta ocupacional), turnos de mañana, tarde y noche, diciembre 2026 con festivos del 8 y el 25.

## Antes de la reunión

```bash
pip install -r requirements.txt
LUNA_DEMO_DATE=2026-12-03 flask --app wsgi run   # abrir http://localhost:5000
```

- Presentar desde esta versión local, no desde el enlace de consulta: ahí aprobar, registrar novedades y escribir libre por WhatsApp no guardan cambios.
- `LUNA_DEMO_DATE` fija el "hoy" del tablero en el día de la reunión (si falta, usa la fecha real dentro de diciembre o el 1 de diciembre).
- Generar una vez antes de entrar para confirmar que todo corre (unos 8 segundos) y luego pulsar **Reiniciar demo** (pie de página).
- Las cifras cambian un poco entre una generación y otra: no citar números exactos de memoria, leerlos de la pantalla.
- Funciona sin internet: todo corre en el portátil.

## Recorrido

| Minuto | Qué mostrar | Mensaje clave |
|---|---|---|
| 0–1 | Inicio vacío: LUNA cuenta cuántas personas, turnos y preferencias hay | "Esto es lo que hoy su coordinación cuadra a mano cada mes." |
| 1–2 | **Generar cuadro** (las frases de espera muestran lo que está revisando) | "LUNA nunca rompe una regla; lo que negocia son las preferencias." |
| 2–4 | La frase de LUNA y las 3 versiones: costo, % de preferencias y noches por auxiliar | "Menor costo ahorra poco y carga de noches a unos pocos. Usted decide qué priorizar." |
| 4–5 | Pulso del hospital: quién está ahora, de día y de noche, en cada servicio. Tocar un día del mes | "Así se ve el hospital las 24 horas, cualquier día del mes." |
| 5–6 | Tocar una persona del Pulso: **¿por qué le tocó?** | "Cada turno tiene una explicación. Se acaban las discusiones de pasillo." |
| 6–7 | **Aprobar y publicar**: avisos por WhatsApp | "LUNA propone, usted aprueba. Nunca publica sola." |
| 7–9 | Para revisar: cambio válido (Aprobar), cambio rechazado (Avisar que no se puede) e incapacidad (Ver reemplazos → Asignar) | "En segundos sabe quién puede cubrir sin pasarse de horas ni quitarle el descanso." |
| 9–10 | Mensajes: escribir como la persona sugerida y usar los ejemplos | "El equipo no instala nada. Pregunta, pide y avisa por WhatsApp." |

Reglas, Equipo y Excel solo si preguntan. Si quieren ver que LUNA se adapta: en Reglas, bajar "días seguidos" a un valor imposible y generar; LUNA dice qué regla lo impide y conserva las versiones anteriores.

## Preguntas para hacerles

1. ¿Cuántas personas y servicios manejan? ¿Quién arma el cuadro y cuánto tiempo le toma?
2. ¿Qué turnos usan (6, 8, 12 horas)? ¿Hay turnos especiales?
3. ¿Qué reglas propias tienen (noches seguidas, fines de semana libres, parejas obligatorias en la noche)?
4. ¿Tienen personal de planta, temporal y por prestación de servicios (OPS)? ¿Son sector público o privado?
5. ¿Cómo manejan hoy los cambios de turno y las incapacidades?
6. ¿Cómo pasan las horas a nómina?

## Qué decir si preguntan

- **¿Las reglas legales están al día?** Están en una tabla con vigencia por fecha y se validan con su área jurídica antes de salir a producción.
- **¿Y los datos del personal?** Se piden con autorización (Ley 1581) y cada clínica tiene su espacio aislado.
- **¿Qué pasa si no hay forma de cumplir todo?** LUNA avisa qué regla o qué cobertura no se puede cumplir para que el coordinador decida.

## Limitaciones de esta versión

- Datos ficticios y estado en memoria: al reiniciar el servidor se pierde lo hecho.
- WhatsApp simulado con un intérprete sencillo.
- Valores legales por verificar.

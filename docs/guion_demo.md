# Guion de la demo (20 minutos)

Demo con una clínica ficticia ("Clínica Demo") de salud mental: hospitalización de agudos e intermedios, 25 personas (auxiliares de enfermería, enfermeras jefe, psiquiatras, psicólogos y terapeuta ocupacional), turnos de mañana, tarde y noche, diciembre 2026 con festivos del 8 y el 25.

## Antes de la reunión

```bash
pip install -r requirements.txt
flask --app wsgi run          # abrir http://localhost:5000
```

- Generar una vez antes de entrar para confirmar que todo corre (toma unos 8 segundos).
- Pulsar **Reiniciar demo** (pie de página) para empezar limpio.
- Sin internet también funciona: todo corre en el portátil.

## Recorrido

| Paso | Qué mostrar | Mensaje clave |
|---|---|---|
| Inicio | Los números: personas, turnos por cubrir, preferencias, reglas | "Esto es lo que hoy su coordinador cuadra a mano cada mes." |
| 1. Su clínica | Servicios, personal mínimo por turno, reglas de ley y de la clínica | "LUNA se adapta a ustedes. Si quieren máximo 2 noches seguidas, se cambia aquí." |
| 2. Su equipo | Habilitaciones, preferencias, prioridad por equidad. Agregar una petición en vivo | "Cada persona dice qué prefiere. Quien el mes pasado salió perdiendo, este mes va primero." |
| 3. Generar | Botón y espera de unos segundos | "LUNA nunca rompe una regla; lo que negocia son las preferencias." |
| 4. Comparar | Tres versiones: costo, % de preferencias, reparto de noches | "Usted decide: más barato, más contento el equipo, o equilibrado. Y sabe el costo antes de la nómina." |
| Cuadro | Calendario por servicio. Tocar un turno → "¿por qué me tocó esto?" | "Cada turno tiene una explicación. Se acaban las discusiones de pasillo." |
| 5. Publicar | Aprobación del coordinador y mensaje de WhatsApp | "LUNA propone, usted aprueba. Nunca publica sola." |
| Novedades | Incapacidad de último minuto → reemplazos legales → asignar | "En segundos sabe quién puede cubrir sin pasarse de horas ni quitarle el descanso." |
| WhatsApp | Preguntar turno, horas, pedir libre, pedir cambio | "El equipo no instala nada. El cambio de turno se valida solo y el jefe aprueba con un clic." |
| Excel | Exportar: cuadro, horas para nómina, resumen | "No tienen que dejar Excel; LUNA les entrega el cuadro y las horas listas para nómina." |

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

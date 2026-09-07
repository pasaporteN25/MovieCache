# Charadas v1 — contrato de datos, generador y dificultad

- **Tarea:** [G1]. Contrato, sin implementación. La implementación es [G2].
- **Fecha:** 2026-09-07.
- **Depende de:** ADR-0005 (dirección móvil), que fija dónde se calcula la dificultad.
- **No es:** [M1]. Esa épica es un catálogo de videojuegos y música — qué poseo, en qué
  consola, qué quiero conseguir. Charadas es una **superficie de juego sobre el catálogo
  audiovisual que ya existe**. No agrega valores a `kind` ni campos a la obra.

## Qué es

Un **generador determinista** de paquetes de títulos para actuar, más un temporizador. Se
juega con uno o dos teléfonos **desincronizados**: eligiendo las mismas opciones, dos
personas obtienen el **mismo paquete**. Saltear un título ya salido es responsabilidad del
jugador, no del sistema.

Consecuencia buscada: **cero estado compartido y cero tiempo real**. No hay WebSocket
—decisión de despliegue ya tomada y documentada en `docs/deployment.md`— ni sesión de
juego en el servidor.

## Qué título se actúa

Decisión necesaria porque una obra tiene varios títulos. El juego usa, en orden:

1. `spanish_title`
2. `title`
3. `original_title`

Se actúa **un solo título**, el mismo para todos los jugadores del paquete, y viaja
resuelto dentro del paquete. Si un jugador viera un título distinto del de su compañero, el
juego se rompe en silencio: el determinismo tiene que cubrir también qué texto se muestra,
no sólo qué obras salen.

Una obra sin ningún título utilizable queda fuera del mazo.

## Mínimo de datos

El owner fijó **300 obras**. El contrato agrega la parte que importa de verdad:

- **300 obras elegibles** en total para habilitar el juego.
- **Al menos 25 por balde de dificultad** para que ese balde se ofrezca.

El total no es el límite real: 300 obras repartidas en cuatro baldes dan ~75 cada uno, pero
si el reparto sale desparejo, **el balde flaco define si el juego funciona**. Un balde por
debajo del mínimo no se ofrece, en vez de ofrecerse y repetir seis títulos.

**Advertencia medida, no teórica.** Un catálogo de autor sesga el mazo entero: Kurosawa,
Tarkovski y compañía caen casi todos en los baldes difíciles. Para que exista un balde
fácil hacen falta títulos masivamente conocidos, que no son los que acumula un catálogo
curado de cinéfilo. Al elegir los directores que se sumen al Club conviene tenerlo presente.

## El generador determinista

La semilla **no puede ser sólo las opciones elegidas**.

"Mismas opciones → mismo mazo" sólo se cumple si los dos teléfonos miran los mismos datos.
Si uno sincronizó y el otro no, las mismas opciones producen mazos distintos y el juego se
rompe sin avisar. Por eso la semilla es:

```
semilla = hash(opciones elegidas + huella del conjunto de obras elegibles)
```

La **huella** es un hash estable sobre los identificadores de las obras elegibles,
ordenados. Cambia cuando cambia el mazo, y sólo entonces.

Esa huella se muestra en pantalla como un código corto legible, para que dos jugadores
verifiquen de un vistazo que están en el mismo mazo antes de empezar. Un mazo distinto es
una condición detectable, no una sorpresa a mitad de partida.

El precedente de implementación ya existe: `back-cover.js` mapea un ID opaco a una de cinco
plantillas estables con un FNV-1a puro. El mazo se arma igual.

## Dificultad

### El hallazgo que define el diseño

Se prototipó una clasificación automática combinando dos señales —qué tan representable es
el título y qué tan conocida es la obra, esta última desde el conteo de votos públicos de
[F6.2]— y se midió contra un corpus de 28 títulos. **No funciona como clasificador**, y el
motivo no es de calibración:

| Obra | Votos | Reconocimiento real |
| --- | --- | --- |
| Los siete samuráis | 370.000 | pocos |
| Batman | 400.000 | todos |
| Relatos salvajes | 190.000 | casi todos (en Argentina) |
| Akira | 190.000 | pocos |
| Rashomon | 180.000 | muy pocos |

Números casi idénticos, percepción opuesta. Ninguna función monótona del conteo de votos
separa esos casos, porque **el conteo mide atención cinéfila global, no reconocimiento en
la sala** — y es ciego a lo cultural: una película argentina que todos conocen acá puntúa
igual que un clásico japonés de autor. Recalibrar la curva mueve los números sin arreglar
el orden.

### La política que sí funciona

En vez de fingir un clasificador, se automatiza sólo lo que es seguro y el resto va a una
persona — la misma disciplina que el proyecto ya aplica al matching (invariante 3), a la
curaduría y a las importaciones.

| Señal | Decisión |
| --- | --- |
| Menos de ~10.000 votos | **Difícil**, automático. Es genuinamente oscura. |
| Más de ~1.000.000 de votos | **Fácil**, automático por notoriedad. |
| Entre medio | **Sugerencia**, no clasificación. Va a revisión humana. |
| Sin datos de votos | Sugerencia por forma del título, siempre revisable. |

La banda intermedia es donde vive casi todo un catálogo real, así que la revisión humana
**no es un plan de contingencia: es el camino principal**, y la interfaz tiene que tratarla
como tal. Una pasada de "repartí estas obras en cuatro baldes", rápida y reanudable, no un
formulario por obra.

### La clasificación manual es autoritativa

Una dificultad puesta por una persona **sobrevive a cualquier recálculo**, exactamente como
`locked_fields` sobrevive al enriquecimiento (invariante 5). Recalcular nunca pisa una
decisión humana; a lo sumo llena lo que nadie decidió.

### Dónde se calcula

**En el servidor.** La señal de notoriedad sale del índice IMDb, que pesa ~1,1 GB y no va a
un teléfono (ADR-0005). La dificultad viaja al cliente como **un campo chico por obra**, ya
resuelto. El teléfono nunca es autónomo para *clasificar*; sí lo es para *jugar*.

## El temporizador

Tres opciones por dificultad, escalando con ella. Tocar la opción arranca la cuenta; se
puede reiniciar.

| Dificultad | Opciones |
| --- | --- |
| Fácil | 1:00 · 2:00 · 3:00 |
| Medio | 1:30 · 2:30 · 4:00 |
| Medio alto | 2:00 · 3:00 · 5:00 |
| Difícil | 3:00 · 4:00 · 6:00 |

Los valores de fácil y medio son los que fijó el owner; los dos últimos extienden la misma
progresión y son ajustables tras jugar. El temporizador es local y no se sincroniza.

## Fuera de alcance de v1

- Estado compartido, sesión de juego, marcador, turnos o cualquier tiempo real.
- Recordar qué títulos ya salieron: es responsabilidad del jugador, por decisión del owner.
- Aprender la dificultad a partir de partidas jugadas. Es tentador y probablemente lo mejor
  a futuro, pero exige guardar resultados y eso reabre el estado compartido.
- Cualquier cambio a `kind`, al esquema portable o a las rutas existentes.

## Qué queda abierto

1. **De dónde salen las obras elegibles.** Catálogo personal, colecciones de Club seguidas,
   o ambas. Importa porque seguir una colección **no copia las obras** (`PRODUCT.md`), así
   que jugar con una colección seguida es un caso distinto de jugar con el catálogo propio.
2. **Si `status` filtra.** ¿Entran las pendientes, o sólo las vistas? Una obra que el dueño
   del teléfono no vio igual puede ser conocida por el grupo.
3. **Cuántos baldes finalmente.** El owner mencionó cuatro "o alguna más". El contrato
   asume cuatro y los umbrales son ajustables sin cambiar la estructura.

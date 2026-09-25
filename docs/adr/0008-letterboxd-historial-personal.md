# ADR-0008: Letterboxd como historial personal

- **Estado:** rechazada como integración; aceptada como importación puntual — 2026-09-07
- **Tarea:** [I1]. Evaluación, sin implementación.
- **Evidencia:** `docs/analisis/i1-radarr-sonarr-letterboxd-2026-09-07.md`
- **Relacionadas:** ADR-0004 (criterio contra scraping), ADR-0006 y ADR-0007.

## Contexto

Letterboxd es la única de las tres integraciones de [I1] que no toca inventario: aporta
**estado personal** —vistas, fechas, puntajes, reviews—, o sea la capa que en Movie Inbox
es del usuario y de nadie más.

Mucha gente tiene años de diario ahí. Poder traerlo es genuinamente valioso.

## Decisión

**No construir un adaptador de Letterboxd.** Traer el historial por el camino de
**importación que ya existe**: un CSV que el owner exporta, con mapeo explícito de columnas
y revisión humana de lo ambiguo.

Sin adaptador, sin credencial, sin host nuevo en la allowlist, sin fuente externa nueva.

## Por qué no un adaptador

### 1. La API no se puede depender de ella

Es **por invitación**. Hay que escribir a `api@letterboxd.com` explicando el uso, leen
todas las solicitudes, no responden individualmente y **no garantizan el acceso**. Una
función del producto no puede apoyarse en algo así: si no aprueban, la función no existe;
si revocan, deja de existir.

### 2. El export no trae ningún identificador

Las columnas de `diary.csv` son exactamente estas:

```
Date, Name, Year, Letterboxd URI, Rating, Rewatch, Tags, Watched Date
```

No hay `tmdbId` ni `imdbId`. La `Letterboxd URI` es un acortador (`boxd.it/...`) o un slug,
y medido contra el propio proyecto ninguna de las dos formas es fuente externa reconocida:

```
https://boxd.it/2a1b                    external_source_name=''  trusted=''
https://letterboxd.com/film/heat-1995/  external_source_name=''  trusted=''
```

### 3. Resolver esa URI sería scraping

La página de la película sí muestra el enlace a TMDb, pero llegar ahí significa abrir el
HTML y leerlo. ADR-0004 ya descartó JustWatch por ese criterio **siendo la fuente original
del dato de disponibilidad**. Aplicar el criterio acá y no allá sería incoherente.

### 4. Exportar cuesta plata

El export de datos de cuenta requiere Letterboxd Pro. No cambia el veredicto técnico, pero
sí quién puede usar la función, y conviene que esté escrito antes de que alguien lo
descubra al intentarlo.

## Por qué sí la importación, y qué se midió

El camino aceptado no es un plan B resignado: está medido y funciona mejor de lo esperado.

**El parser existente ya lee el archivo.** Las filas se parsean sin tocar nada; `Name` y
`Year` caen solos en `title` y `year` por `CSV_ALIASES`. `Watched Date` y `Rating` necesitan
un `column_map` explícito, que la importación ya soporta.

**El emparejamiento por título alternativo funciona.** Era el riesgo más obvio —el export
trae el título en inglés, la ficha del owner lo tiene en castellano— y no se materializa:

```
"The Secret in Their Eyes" (2009) contra "El secreto de sus ojos":
  accepted=True  reason=exact_title_year  score=1.0
```

**El riesgo que sí queda es el homónimo**, y por eso esto no puede correr solo:

```
homonimo sin IDs del lado entrante: accepted=True  reason=exact_title_year
```

Dos obras distintas con el mismo título y el mismo año se aceptan como la misma, y el CSV
no tiene con qué desempatar. Es el mismo techo que ya tiene cualquier importación de TXT
—no una regresión— pero fija la condición de abajo.

## Condiciones de la aceptación

1. **Persona en el medio, siempre.** Una importación de Letterboxd no se aplica sola. Es
   precisamente el caso que el invariante 3 describe: sin identificador que desempate, lo
   dudoso va a revisión.
2. **Nada se escribe hacia Letterboxd.** La dirección es de entrada. Marcar vistas o subir
   puntajes al servicio queda fuera de esta decisión, y sería otra decisión con otras
   consecuencias de privacidad.
3. **El puntaje de Letterboxd es el puntaje del owner.** A diferencia de [F6.2], donde un
   puntaje público nunca toca `rating`, acá el número **es** la opinión de la persona y su
   lugar natural es `rating`. Vale la pena decirlo porque las dos reglas conviven y parecen
   contradictorias: la diferencia es de quién es la opinión, no de dónde viene el dato.
   Conversión pendiente: Letterboxd puntúa en estrellas de 0,5 a 5, el catálogo de 1 a 10.
4. **Nada personal sale de la instancia.** Se lee un archivo que el owner ya bajó. Leer no
   es publicar.

## Qué queda abierto

1. **Si hace falta trabajo, o ya alcanza.** El parser lee el archivo hoy con un `column_map`
   armado a mano. Falta decidir si eso es suficiente o si merece un preset con nombre —
   "importar de Letterboxd"— que arme el mapeo solo. Es chico, y es lo único con código por
   delante de esta decisión.
2. **`Rewatch` y `Tags` no tienen destino.** Ninguna de las dos columnas tiene equivalente
   en el catálogo. Descartarlas es aceptable; conviene decirlo en pantalla en vez de que
   desaparezcan en silencio.
3. **Conversión de la escala de puntaje**, con el redondeo explícito y no inferido.
4. **`Date` contra `Watched Date`.** La primera es cuándo se registró, la segunda cuándo se
   vio. `watched_at` quiere la segunda; usar la primera por descuido corrompería fechas
   reales del usuario.

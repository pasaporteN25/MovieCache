# [MB2] Auditoría móvil — línea de base medida

**Fecha:** 2026-09-07. **Alcance:** la mitad medible de [MB2]. La prueba con usuarios
reales necesita personas con teléfonos y queda como protocolo al final.

**Los arreglos no son de este frente.** Esto mide y nombra; corregir la presentación
móvil corresponde al frente visual.

## Método

Chromium bajo Playwright con **emulación real de dispositivo** —`is_mobile`, touch,
`device_scale_factor` 3 y user agent de Android— a 390×844 y 320×720, sobre una instancia
descartable con 21 obras sintéticas, incluidas una de título deliberadamente extenso y
sinopsis de largo realista. No se usó el catálogo personal del owner.

Se midió por superficie: desborde horizontal de la página, objetivos táctiles por debajo
de 44 px, texto por debajo de 12 px y elementos que se salen de su contenedor.

### Límite de la primera pasada, y por qué importa

La primera medición **exageró**, y conviene decirlo porque el número crudo invita a
conclusiones falsas:

- Contaba el `<input>` de un checkbox como objetivo táctil. Pero un checkbox dentro de un
  `<label>` tiene un objetivo real mucho mayor. Medido: `randomCatalogOnly`,
  `externalSource` y `searchByDirector` miden 13 px de input y **44–56 px de objetivo
  efectivo**. Los tres estaban bien.
- Contaba como texto chico los rótulos decorativos: placeholders de miniatura, "Fotograma
  01/02" de la contratapa, kickers. En Colección, **276 de 285** hallazgos eran de ese
  tipo.

Los números de abajo son los de la segunda pasada, ya separando decoración de contenido.

## Resultados

| Superficie | Desborde 390 | Desborde 320 | Táctil real < 44 px | Texto de contenido < 12 px |
| --- | --- | --- | --- | --- |
| Inicio | 0 | 0 | 0 | 9 |
| Colección | 0 | 0 | **0** | **9** |
| Ficha | 0 | 0 | **0** | pocos |
| Club | 0 | 0 | 0 | 16 |
| **Bandeja** | **317 px** | **387 px** | **1** | **53** |

## El hallazgo: Bandeja es la única superficie con problemas reales

Es el eslabón que se anticipó al leer los breakpoints —Bandeja rompe recién en 700–1120 px—
y ahora está medido.

1. **Desborde horizontal de 317 px a 390, y 387 px a 320.** Es la única superficie que
   desborda. Cuatro elementos se salen de su contenedor: `NAV.primary-nav`,
   `HEADER.curation-heading`, `NAV.inbox-mode-tabs` y `DIV.scope-strip`. Un desborde
   horizontal en un teléfono no es un detalle estético: hace que la página se pueda barrer
   de costado y que los controles queden fuera de vista.
2. **53 nodos de contenido real por debajo de 12 px**, a 10 px: tipos de caso, contadores
   ("21 casos"), metadatos de obra ("1968 · película"). No son decorativos; es la
   información que hay que leer para decidir en la cola.
3. **Un control táctil genuinamente chico:** `persistCurationHistory`, 38 px de objetivo
   efectivo contra el piso de 44.

## Lo que está bien, y por qué el número crudo se veía peor

**Inicio y Club están limpios.** Inicio lo confirma como trabajo bien hecho: es la
superficie que [U2-R.6] auditó y reparó, y se nota en la medición.

**Colección y Ficha están sanas** una vez descontada la decoración y los inputs envueltos
en label: cero desborde y cero objetivos táctiles reales por debajo del piso. Lo único que
queda son nueve rótulos secundarios a 10 px —"Década", "Género", "Dirección", "Fuente"—,
que el propio gate de [U2-R.7a] ya aceptó a ese tamaño para metadatos secundarios.

## Lo que esto no midió

Ser explícito importa, porque una medición verde no es una interfaz usable:

- **Si se entiende.** Ninguna métrica dice si alguien encuentra cómo agregar una obra.
- **Alcance del pulgar.** Un control puede medir 44 px y estar en una esquina incómoda.
- **Táctil real** contra emulado: gestos, scroll con inercia, teclado tapando campos.
- **Lectura al sol, con una mano, apurado**, que es cómo se usa un teléfono de verdad.
- **Lectores de pantalla en un dispositivo real.**

## Protocolo para la prueba con personas

Lo que hace falta para la mitad que no puedo hacer.

**Antes:** servir por HTTPS según `docs/deployment.md` —sin eso un teléfono ajeno no
entra—, y crear las cuentas de antemano, porque no hay registro público.

**Cuatro tareas, sin ayudar, cronometradas y observando dónde dudan:**

1. "Buscá una película que te guste y decime si está disponible."
2. "Agregá una película que no esté."
3. "Marcá una como vista y ponele puntaje."
4. "Encontrá algo para ver esta noche."

**Qué anotar:** dónde dudan más de tres segundos, qué tocan que no es tocable, si giran el
teléfono, si hacen zoom, y qué dicen en voz alta. **No** anotar opiniones sobre estética:
esa pregunta se responde sola y no es la que interesa.

**Sesgo a tener presente.** Lo que se testea es una adaptación de un diseño pensado para
escritorio. Si alguien tropieza, la conclusión es "esto no funciona en el teléfono", **no**
"esta dirección visual está mal". Son dos hallazgos distintos y conviene no confundirlos.

**Y no empezar por Bandeja.** Está medida como rota; hacer tropezar a alguien con un
desborde conocido gasta la sesión sin aprender nada nuevo.

## Consecuencia para ADR-0005

La auditoría respalda una decisión ya tomada. Bandeja es Scanner y Curaduría, o sea la
**capa operativa** —rutas, bibliotecas, colas de decisión— que ADR-0005 dejó explícitamente
fuera del cliente móvil. Que sea justo la superficie que peor se comporta en un teléfono
refuerza que ahí no debe ir. Su arreglo importa para la web en un teléfono, no para el
cliente Android.

# Inicio: videoclub material v2

> **Referencia histórica.** U2 implementó este brief, pero su resultado visual no fue
> aceptado el 2026-09-03. La dirección vigente para la recuperación de Inicio es
> `docs/briefs/home-videotheque-recovery-v1.md`, acompañada por la lámina versionada
> `docs/design/u2-recovery-north-star-v1.png`. Este archivo se conserva para explicar
> las decisiones y contratos técnicos que sí pueden reutilizarse.

## Referencia durable

La dirección proviene de la «lámina generada 1» mencionada durante la definición de
Inicio. Esa lámina fue una referencia conversacional y no se versionó como archivo del
repositorio; por lo tanto no debe tratarse como un asset que pueda enviarse al navegador.
Este brief preserva las decisiones visuales y de interacción necesarias para que una
sesión futura no invente una interpretación distinta. Si se conserva o se vuelve a
adjuntar la lámina, debe agregarse como referencia de diseño, con procedencia y licencia,
nunca como contenido de una obra.

## Trabajo y dirección

- Una persona abre Inicio para elegir qué ver de su propia biblioteca. El modo es
  **explorar**: la programación editorial debe orientar sin ocultar disponibilidad ni
  convertir la pantalla en un panel administrativo.
- La parte superior es `Cartelera disponible`: ambiente de *noche de cine*, imagen
  original/licenciada y una lista compacta de obras, semejante a una lista de Winamp de
  reproducción. Las flechas recorren la lista; Home/End saltan a sus extremos y Enter
  confirma la obra cuyo contexto se muestra. Puntero y touch ofrecen el mismo resultado
  sin ser la única forma de usarla.
- La parte inferior reúne las categorías editoriales ya existentes —por ejemplo
  `Disponible esta noche`, `Tu archivo pide memoria` y rutas por director/género— como
  estanterías físicas horizontales. En el escenario de escritorio hay una categoría
  activa a la vez, elegida mediante un selector de estanterías: no se apilan todas las
  filas y no se obliga a hacer scroll vertical para llegar a ellas. Cada obra se ve
  primero por su **lomo**, no por una portada frontal: el conjunto debe parecer una
  repisa real y permitir reconocer foco, título y disponibilidad.
- Al seleccionar un lomo aparece una **previsualización** que reutiliza el marco
  `vhs-cassette-frame-v1.png`, con caja frontal/portada, razón editorial, metadatos y
  lectura extendida suficiente para decidir. `Ver más` abre la transición de caja al
  dossier donde el cassette VHS negro acompaña la información completa. El cassette y
  cualquier textura son decoración accesible con `aria-hidden`; identidad, metadatos y
  acciones siempre se conservan como HTML vivo.
- La previsualización y el dossier exponen `Editar mi ficha` como acción secundaria sólo
  cuando la obra y la persona tienen permiso. Editar no se mezcla con elegir ni con abrir
  la caja; obras de Club o superficies de sólo lectura jamás muestran una mutación
  engañosa.
- Un **mostrador de control** propio del escenario integra destinos (`Inicio`,
  `Colección`, `Bandeja`, `Club`) y utilidades (`Buscar`, `Agregar`, `Usuario`) sin que
  una barra genérica quede ajena a la pantalla. Destinos y comandos se distinguen, sus
  rutas y atajos se mantienen y cada acción continúa siendo visible y alcanzable.

## Límites de implementación

- Reutilizar el payload editorial, acciones y contratos actuales de Inicio; U2 no abre
  rutas, no cambia `/api/home`, no convierte la cartelera pública en una vista privada y
  no inicia el cliente Android.
- `Noche de cine` necesita ser un asset nuevo, original o con licencia verificable:
  sin logotipos, actores reconocibles, textos, títulos de obras ni datos de una instancia.
  El fondo inicial existe en `static/img/night-cinema-ambient-v1.png`; su
  prompt/procedencia/hash están auditados en `docs/assets/night-cinema-ambient-v1.md`.
  Versiones posteriores siguen el mismo mecanismo que `vhs-cassette-frame-v1.png`.
- La transformación visual no puede depender de hover. Debe mantener Tab sin trampas,
  foco visible, Enter, Escape en el dossier, `prefers-reduced-motion`, navegación táctil
  y equivalentes legibles para una a cuatro recomendaciones, filas vacías, imágenes que
  fallen, títulos extensos y pantallas móviles.
- En el viewport de escritorio objetivo, Inicio se compone como una escena completa sin
  scroll vertical: cartelera, mostrador y una estantería seleccionada quedan dentro de
  la altura disponible; las bibliotecas recorren sus lomos lateralmente. No se bloquea
  el scroll vertical si la altura es insuficiente, hay teclado virtual, se usa móvil o
  zoom alto: en esos casos la prioridad es conservar contenido y controles accesibles.

## Secuencia de validación

1. U2.0 resuelve el mostrador de control antes de mover navegación o utilidades.
2. U2.1 prueba la nueva cartelera Winamp y su ambiente sin modificar la semántica
   editorial.
3. U2.2 sustituye las tiras de cassettes frontales por lomos y previsualización VHS.
4. U2.3 conecta la apertura de caja con el dossier VHS extendido.
5. U2.4 conecta y prueba la entrada explícita a edición usando permisos reales.

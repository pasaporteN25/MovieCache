# movie-inbox-android — plan inicial (capturado 2026-08-17)

> Esto es una foto de dónde quedó una conversación sobre v0.5.0, no un plan
> ejecutable ni una arquitectura aprobada. Lo natural es retomarlo en una sesión
> nueva —posiblemente en un repo `movie-inbox-android` separado de este— y
> replantear cada punto de abajo con el código real de ese momento delante, no con
> lo que dice este archivo.

## La idea, tal como la planteó Lucas

No es un cliente delgado que solo lee datos mientras el servidor Docker está
prendido. Es una app que funciona sin depender de que la información generada por
la instancia self-hosted esté disponible en el momento, pero que si el teléfono
está en la misma red local o conectado por VPN, accede a los datos reales de esa
instancia (y probablemente sincroniza cambios en ambas direcciones).

Eso es un modelo de datos con estado local persistente + sincronización oportunista,
no una vista remota. Cambia bastante el problema.

## Por qué es más grande que lo que dice hoy `docs/roadmap.md`

La sección `v0.5.0: cliente basico` de `docs/roadmap.md` dice explícitamente:

> Sin administración, Scanner, importaciones, curaduría avanzada ni **uso offline**
> en la primera entrega.

O sea que el roadmap actual excluye justo la parte que hace interesante a esta
idea. Cuando se retome esto en serio, `docs/roadmap.md` necesita una revisión real
de qué significa v0.5.0 (o si pasa a ser una versión distinta, dado que ya no es
"básico") — no alcanza con sumar una viñeta.

## Por qué como proyecto aparte

Kotlin/Gradle/Android Studio es un toolchain completamente distinto al de este
repo (Python + FastAPI + frontend vanilla). Meterlo en el mismo repo mezclaría CI,
convenciones de capas (`CLAUDE.md`) y ciclo de release de dos cosas que no
comparten nada más que hablar HTTP entre sí. Un repo `movie-inbox-android` (nombre
tentativo) aparte es la elección consistente con por qué este mismo repo ya separa
`domain/`/`application/`/`web/` — no mezclar lo que tiene razones distintas para
cambiar.

Lo que **sí** queda en *este* repo, sin importar dónde viva la app: la capa
`/api/v1/` y el esquema de auth que el cliente Android va a consumir. Ese trabajo
es del backend self-hosted, no del cliente.

## Abierto — para la próxima sesión que retome esto

1. **Modelo de datos offline.** ¿Qué vive en el teléfono cuando no hay
   conectividad — todo el catálogo personal, un subconjunto reciente, solo lo que
   el usuario marcó? ¿Qué motor local (SQLite vía Room, algo más simple)?
2. **Estrategia de sync.** Oportunista cuando detecta LAN/VPN, ¿con qué
   granularidad? Si el usuario edita estado/fecha/puntaje/review offline y la
   misma ficha cambió del lado del servidor mientras tanto, ¿quién gana? Esto no
   existía como problema en un cliente de solo lectura remota — con estado local
   editable, la resolución de conflictos es real.
3. **Esquema de auth.** Sigue en pie el análisis de la sesión del 2026-08-17: hoy
   el servidor depende de un `api_token` único por proceso + cookie + allowlist de
   `Origin` (`src/movie_inbox/web/security.py`, `web/dependencies.py`), pensado
   para un browser con una pestaña. Un cliente nativo necesita login por
   usuario + token de larga duración por dispositivo (patrón Jellyfin/Immich), sin
   importar si termina siendo online-only u offline-first.
4. **Certificados.** Si el acceso es siempre LAN/VPN, un certificado autofirmado
   (con aceptación explícita del usuario) es razonable y común en setups
   self-hosted. Si en algún escenario hay acceso por dominio público, la respuesta
   cambia. Depende de qué tan cerrado sea el modelo de red que se termine
   eligiendo en el punto 2 — repreguntar en vez de asumir.
5. **Qué sincroniza y qué no.** El roadmap actual excluye administración, Scanner,
   importaciones y curaduría avanzada de la "primera entrega". Con este cambio de
   alcance (offline + sync), ¿esa exclusión se mantiene igual, o cambia qué es
   "básico"?

## Nota aparte, no mezclar: catálogos públicos / API pública

Punto distinto que salió en la misma conversación: la idea de usar `/api/v1/` para
exponer información y "empezar a formar catálogos propios" — datos públicos que
otros puedan consumir, no solo el propio dispositivo autenticado del dueño.

Esto es una superficie de API con una postura de privacidad totalmente distinta a
la de arriba (pública/anónima vs. autenticada por usuario) y toca directo el
invariante de privacidad de `CLAUDE.md` (`Club` nunca expone rutas, archivos
locales, notas ni estado operativo — sin excepción para el owner). Antes de
diseñar nada acá hace falta investigar qué campos del catálogo son seguros para
exponer públicamente. Tratarlo junto con el auth del cliente Android sería mezclar
dos problemas con reglas de acceso distintas — mejor como su propio hilo de
diseño, aunque probablemente ambos terminen viviendo bajo el mismo prefijo
`/api/v1/`.

## Qué NO es este documento

No es una arquitectura aprobada, no tiene tareas para ejecutar, y nadie debería
escribir código a partir de esto sin una sesión de diseño dedicada primero (posible
candidata para el "otro agente" que mencionó Lucas al pedir que esto se guarde para
después).

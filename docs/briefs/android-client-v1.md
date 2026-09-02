# Cliente Android v1: corte de A2

## Propósito

El cliente Android consume únicamente la Device API v1 de la misma instancia Movie Inbox.
No reemplaza la interfaz web ni permite Scanner, administración, Club, importaciones,
cartelera pública u operaciones masivas.

## Entregas

| Parte | Entrega | Fuera de alcance |
| --- | --- | --- |
| A2.1 | App Compose nativa, URL de instancia HTTPS, login, refresh, logout y token seguro | catálogo, modo offline, configuración administrativa |
| A2.2 | Catálogo paginado, búsqueda local, detalle y disponibilidad de solo lectura | edición, fuentes externas, inventario detallado |
| A2.3 | `PATCH` de estado/fecha/puntaje/review y gate de ciclo de vida/compatibilidad | Scanner, administración, Club, cambios de metadata, sincronización offline |

## Decisiones de A2.1

- Android nativo, Kotlin y Compose; no se crea una promesa multiplataforma antes de que el
  MVP valide la experiencia móvil.
- Hilt con KSP, coroutines/`StateFlow`, Retrofit/OkHttp y `kotlinx.serialization`.
  El repositorio es el límite de errores: la UI no recibe excepciones de red ni DTOs.
- La app acepta una URL HTTPS de instancia con certificado válido. Una configuración de
  red separada permite `http://10.0.2.2` exclusivamente en el build `debug`, para probar
  un servidor local desde el emulador; release no permite HTTP ni certificados omitidos.
- Access y refresh token se guardan por instancia con Android Keystore; nunca se escriben
  en preferencias sin cifrar, logs, analytics, URI, clipboard ni backups. El interceptor
  agrega `Authorization: Bearer` a las rutas v1 autenticadas y falla localmente si falta
  un access token.
- El refresh rota ambos tokens una única vez ante `401`; si falla, borra la sesión local y
  vuelve al login. No se reintenta una mutación automáticamente después de un `PATCH`.
- La app ignora campos opcionales desconocidos de v1, respeta `X-Movie-Inbox-Api-Version`
  y no usa ni depende de `/api/` histórico, cookies o `X-Movie-Inbox-Token`.

## Gate de entorno

Antes de generar el proyecto, la máquina de desarrollo debe tener JDK 17+ y Android SDK
con una plataforma instalada y expuesta a Gradle. El repositorio actual no trae Gradle
Wrapper ni un módulo Android, por lo que no se considera válido declarar A2.1 terminado
hasta compilar `assembleDebug` y ejecutar sus pruebas unitarias.

# Mis dispositivos

Modo: Operate. Extensión del menú de la cuenta dentro del estilo vigente.
Cada cuenta genera su QR y lista/revoca sus propios teléfonos; no es administración
de dispositivos de otros miembros.

## Direction contract

THESIS: llevar el catálogo de esa cuenta al teléfono con una acción reconocible.
OWN-WORLD: heredar tipografía, controles y colores del diálogo de cuenta existente.
STORY: abrir Mis dispositivos, generar QR, escanear en Android; reconocer un teléfono
por su nombre y última actividad, confirmar antes de revocarlo.
FIRST VIEWPORT: título y cierre, acción de conexión, QR con cuenta/origen/vence,
lista debajo. En mobile se apila y permite scroll sin desbordar el viewport.
FORM: extensión acotada del menú y diálogo existente; no corresponde sorteo de conceptos.
FINISH: revisión de capturas desktop/mobile, pruebas de interacción y alcance documentado.

## Criterios

- Accesible para owner/miembro. Backend conserva aislamiento por cuenta.
- No generar QR al abrir ni guardar tickets en URL, storage o logs.
- Ocultar/eliminar la imagen al vencer y al cerrar. Desechar respuestas tardías.
- HTTPS sin configurar y dibujo fallido explican cómo reintentar.
- Revocar pide confirmación con nombre concreto; cancelar conserva acceso.
- La fecha de actividad no se presenta como último sync confirmado.

## Evidencia

2026-10-05: tres pruebas de navegador de dispositivos, 47 regresiones de interfaz
en la misma ejecución y 38 pruebas del backend de pairing pasan. Capturas 1280/390
en `docs/design/devices/`; QR y catálogo sintéticos, nunca datos del owner.
Revisión visual: jerarquía legible, controles táctiles, sin overflow horizontal.
El detalle de expiración del QR usa epoch en segundos y account como string,
según el contrato real. La réplica y Keystore se prueban en el repo Android.

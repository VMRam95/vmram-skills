# Fitness functions — <PROYECTO>

Invariantes **ejecutables**. Convención: listan violaciones · salida vacía es OK · `exit != 0`
falla en CI. Herramienta: <FF_TOOL>.

> **Bloqueante vs aviso.** En proyecto con historia, empieza en aviso: arrancar todo bloqueante
> rompe el CI el día uno. En proyecto nuevo, al revés: nacen bloqueantes con baseline cero, que es
> el mejor momento posible. Promocionar un aviso a bloqueante es decisión humana, vía ADR.

## Reglas

| # | Regla | Sujetos | Baseline | Modo |
|---|---|---|---|---|
| 1 | _(sembrar)_ | | | |

**Sujetos** es el número de elementos que la regla evalúa de verdad. **Si es 0, la regla está dando
un falso verde**: apunta a algo que no existe.

## Al medir el baseline, tres trampas

1. **Falso verde** — regla que apunta a un paquete inexistente "pasa vacía". Verifica sujetos > 0.
2. **Clasificar por un ancestro** en vez de por la frontera efectiva.
3. **No caminar la indirección** — herencia transitiva, alias de import. Un grep ingenuo los pierde.
   Si conviven dos mecanismos para el mismo invariante, valida la forma correcta de cada uno.

## Cómo se corre

```bash
<COMANDO_FITNESS>
```

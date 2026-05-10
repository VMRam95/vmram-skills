---
name: presupuesto
description: |
  Generate professional project budgets/quotes in markdown format.
  Supports fixed price, commission-based, or dual-option quotes.
  Auto-calculates totals, discounts, payment milestones.
  Trigger phrases: "presupuesto", "generar presupuesto", "budget", "quote", "crear presupuesto", "/presupuesto"
---

# Presupuesto - Professional Budget Generator

Generate professional, detailed project budgets in markdown format following a proven template. Supports fixed-price, commission-based, or dual-option quotes with automatic calculations.

## Arguments

```
/presupuesto [output-path]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| output-path | No | `./docs/client/` | Directory where budget files will be saved |

## Examples

```bash
/presupuesto                              # Interactive mode, saves to ./docs/client/
/presupuesto ./presupuestos/              # Custom output directory
```

## Implementation

### Step 1: Gather Client Information

Use **AskUserQuestion** to collect basic project info:

**Question 1 - Client & Project:**
- Client name
- Client email (optional)
- Project name / description (1-2 sentences)
- Date (default: today)
- Quote validity (default: 30 days)

### Step 2: Gather Pricing Model

Use **AskUserQuestion** to determine pricing structure:

**Question 2 - Pricing Model:**
- **Option A only** - Fixed price, no recurring fees
- **Option B only** - Reduced price + monthly commission
- **Both options** - Generate two documents for client to choose (recommended)

If commission model selected, ask:
- Commission percentage (default: 5%)
- Commission basis (e.g., "monthly revenue from classes", "monthly SaaS revenue")

### Step 3: Gather Existing Work (POC)

Use **AskUserQuestion**:

**Question 3 - Existing Work:**
- Is there existing work / POC already done? (Yes/No)
- If yes, ask for description and estimated hours
- Hourly rate (default: €40/h)

### Step 4: Gather Modules / Features

This is the core of the budget. Ask the user to describe the work to be done.

**Question 4 - Modules:**

Ask the user to list modules/features. For each one, collect:
- Module name
- Brief description
- Estimated hours
- (Rate is inherited from Step 3 unless overridden)

Present them in a table and ask for confirmation. Allow adding/removing/editing.

Example format:
```
| Module | Description | Hours | Rate | Amount |
|--------|-------------|-------|------|--------|
| Admin Dashboard | User management, metrics | 18h | €40/h | €720 |
| Payment System | Stripe integration, invoicing | 14h | €40/h | €560 |
| ...
```

### Step 5: Gather Additional Details

Use **AskUserQuestion** for each:

**5a - Discounts:**
- Apply discount? (Yes/No)
- If yes: percentage and description (e.g., "20% early client discount")

**5b - What's Included:**
Suggest standard inclusions (user can modify):
- Source code ownership
- X months maintenance (default: 6)
- X training sessions (default: 2 x 1h)
- Technical documentation
- Email support during development

**5c - What's NOT Included:**
Ask user for exclusions. Suggest common ones:
- Native mobile app (iOS/Android)
- Data migration from external systems
- Integrated payment gateway
- 24/7 phone support

**5d - Recurring Costs (client pays):**
Ask for external services the client will pay for monthly:
```
| Service | Estimated Cost | Notes |
|---------|----------------|-------|
| Hosting | €0-20/month | e.g., Vercel free tier |
| Database | €0-25/month | e.g., Supabase free tier |
```

**5e - Timeline:**
Ask for development milestones:
```
| Milestone | Timeline | Deliverable |
|-----------|----------|-------------|
| Milestone 1 | Month X | Description |
| Milestone 2 | Month Y | Description |
| Final Delivery | Month Z | Full project |
```

**5f - Payment Schedule:**
Suggest standard split (user can modify):
- 40% at contract signing
- 30% at intermediate milestone
- 30% at final delivery

### Step 6: Calculate Totals

Perform all calculations automatically:

#### For Fixed Price (Option A):

```
POC_SUBTOTAL = poc_hours × hourly_rate
FEATURES_SUBTOTAL = sum(module_hours × rate) for each module
AUTONOMY_PREMIUM = calculated to reach desired total (typically 30-40% markup for no-commission model)
GROSS_TOTAL = POC_SUBTOTAL + FEATURES_SUBTOTAL + AUTONOMY_PREMIUM
DISCOUNT = GROSS_TOTAL × discount_percentage
FINAL_TOTAL = GROSS_TOTAL - DISCOUNT
```

Payment milestones:
```
PAYMENT_1 = FINAL_TOTAL × 0.40 (at signing)
PAYMENT_2 = FINAL_TOTAL × 0.30 (mid milestone)
PAYMENT_3 = FINAL_TOTAL × 0.30 (delivery)
```

#### For Commission Model (Option B):

```
POC_SUBTOTAL = poc_hours × hourly_rate
FEATURES_SUBTOTAL = sum(module_hours × rate) for each module
BASE_TOTAL = POC_SUBTOTAL + FEATURES_SUBTOTAL
COMMISSION_DISCOUNT = BASE_TOTAL × 0.20 (20% discount for commission model)
FINAL_TOTAL = BASE_TOTAL - COMMISSION_DISCOUNT
MONTHLY_COMMISSION = commission_percentage% of monthly revenue
```

Commission examples table:
```
| Monthly Revenue | Commission (X%) |
|-----------------|-----------------|
| €3,000 | €150 |
| €5,000 | €250 |
| €10,000 | €500 |
| €15,000 | €750 |
| €20,000 | €1,000 |
```

### Step 7: Generate Budget Document(s)

Generate markdown files using the template below. If both options were selected, generate TWO separate files.

**File naming:**
- Single option: `presupuesto-{{project-slug}}.md`
- Option A: `presupuesto-{{project-slug}}-opcion-a.md`
- Option B: `presupuesto-{{project-slug}}-opcion-b.md`

### Step 8: Show Summary

Display to user:
- Files created (with paths)
- Total amounts for each option
- Quick comparison table (if both options)
- Remind about payment schedule

---

## Document Template

### Template: Fixed Price (Option A)

```markdown
# Presupuesto Desarrollo {{PROJECT_NAME}}

## {{PROJECT_TITLE}} - Precio Cerrado (Sin Comisiones)

**Fecha:** {{DATE}}
**Cliente:** {{CLIENT_NAME}}
**Proyecto:** {{PROJECT_DESCRIPTION}}

---

## Resumen Ejecutivo

{{EXECUTIVE_SUMMARY}}

| Concepto | Importe |
|----------|---------|
| **Total Desarrollo** | **€{{TOTAL}}** |
| **Comision Mensual** | **Ninguna** |

---

## Desglose del Desarrollo

### Base Tecnologica (POC)

| Concepto | Horas | Tarifa | Importe |
|----------|-------|--------|---------|
| {{POC items listed here}} |
| **Subtotal POC** | **{{POC_HOURS}}h** | **€{{RATE}}/h** | **€{{POC_SUBTOTAL}}** |

### Nuevas Funcionalidades

| Modulo | Descripcion | Horas | Importe |
|--------|-------------|-------|---------|
| {{Each module row}} |
| **Subtotal Funcionalidades** | | **{{FEAT_HOURS}}h** | **€{{FEAT_SUBTOTAL}}** |

### Prima de Autonomia

| Concepto | Importe |
|----------|---------|
| Propiedad total sin vinculacion futura | €{{PREMIUM}} |
| Sin comisiones ni pagos recurrentes al desarrollador | Incluido |
| **Subtotal Prima** | **€{{PREMIUM}}** |

### Resumen Economico

| Concepto | Importe |
|----------|---------|
| POC (Base tecnologica) | €{{POC_SUBTOTAL}} |
| Nuevas funcionalidades | €{{FEAT_SUBTOTAL}} |
| Prima de autonomia | €{{PREMIUM}} |
| **SUBTOTAL** | **€{{GROSS_TOTAL}}** |
| {{DISCOUNT_DESCRIPTION}} | -€{{DISCOUNT_AMOUNT}} |
| **TOTAL DESARROLLO** | **€{{FINAL_TOTAL}}** |

---

## Incluido en el Precio

### Desarrollo
{{INCLUDED_DEV_ITEMS}}

### Seguridad
{{INCLUDED_SECURITY_ITEMS}}

### Soporte y Mantenimiento
{{INCLUDED_SUPPORT_ITEMS}}

---

## No Incluido

{{EXCLUDED_ITEMS}}

---

## Costes Mensuales Recurrentes

*A cargo del cliente una vez entregado el proyecto:*

| Servicio | Coste Estimado | Notas |
|----------|----------------|-------|
| {{RECURRING_COSTS}} |
| **TOTAL ESTIMADO** | **{{RECURRING_TOTAL}}** | |

---

## Forma de Pago y Calendario

| Pago | Concepto | Importe | Fecha |
|------|----------|---------|-------|
| **Inicial** | {{PAYMENT_1_DESC}} | €{{PAYMENT_1}} | {{PAYMENT_1_DATE}} |
| **Hito 1** | {{PAYMENT_2_DESC}} | €{{PAYMENT_2}} | {{PAYMENT_2_DATE}} |
| **Hito 2** | {{PAYMENT_3_DESC}} | €{{PAYMENT_3}} | {{PAYMENT_3_DATE}} |
| | **TOTAL** | **€{{FINAL_TOTAL}}** | |

---

## Hitos de Desarrollo

{{MILESTONES}}

---

## Validez

Este presupuesto tiene una validez de **{{VALIDITY}} dias** desde la fecha de emision.

---

*Presupuesto elaborado por Victor Manuel Ramirez Marcos*
```

### Template: Commission Model (Option B)

Same structure as Option A but with these differences:

1. **Title:** `{{PROJECT_TITLE}} - Precio Reducido + Comision`
2. **Resumen Ejecutivo table:** Shows commission percentage instead of "Ninguna"
3. **No "Prima de Autonomia" section**
4. **Add "Modelo de Comisiones" section** after Resumen Economico:

```markdown
## Modelo de Comisiones

La comision del {{COMMISSION_PCT}}% se aplica sobre {{COMMISSION_BASIS}}.

### Ejemplos de Comision Mensual

| Facturacion Mensual | Comision ({{COMMISSION_PCT}}%) |
|---------------------|-------------------------------|
| €3.000 | €{{calc}} |
| €5.000 | €{{calc}} |
| €7.500 | €{{calc}} |
| €10.000 | €{{calc}} |
| €15.000 | €{{calc}} |
| €20.000 | €{{calc}} |

### Sistema de Tracking
- Calculo automatico basado en {{COMMISSION_BASIS}}
- Informe mensual transparente
- Factura emitida a mes vencido
```

5. **Discount section:** Shows commission-model discount (typically 20%) instead of autonomy premium
6. **Payment table:** Adds monthly commission row
7. **Included section:** Adds "Sistema de tracking para calculo transparente de comisiones"

---

## Calculation Rules

### Autonomy Premium (Option A only)
The premium compensates for not receiving recurring commission income. Calculate as:
- `PREMIUM = (POC_SUBTOTAL + FEAT_SUBTOTAL) × 0.35` (approximately)
- Adjust so the final total (after discount) is a clean, round number
- The premium should make Option A cost roughly 1.8-2x Option B

### Commission Discount (Option B only)
- Apply 20% discount on POC + Features subtotal
- This makes the initial investment significantly lower than Option A

### Rounding
- All amounts should be rounded to nearest whole euro
- Payment milestones should sum exactly to the total
- Adjust the last payment if rounding creates a difference

---

## Notes

- All amounts are in EUR unless stated otherwise
- The skill generates markdown files ready to be converted to PDF or sent directly
- Always show calculations to the user before generating files for verification
- If the user has an existing presupuesto format they prefer, adapt to it
- The template is a guide - adjust sections based on project needs (some sections may not apply)
- For projects without a POC, skip that section entirely
- Spanish is the default language for the budget content (matching client-facing needs)

## Error Handling

- If output directory doesn't exist, create it
- If files already exist, ask user before overwriting
- If user provides incomplete info, use sensible defaults and flag them
- Validate that hours × rate calculations match stated subtotals

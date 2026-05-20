# Análise do Banco de Dados — LIDDIS

## Resumo Geral

**Status:** ✅ Estrutura sólida com ajustes aplicados  
**Banco:** PostgreSQL (Supabase em produção, SQLite em dev)  
**Padrão:** UUID como PK em todos os models principais  
**LGPD:** Soft delete + AuditLog implementados  

---

## Análise por Model

### ✅ Organization (users)
| Campo | Tipo | Status |
|-------|------|--------|
| id | UUID PK | ✅ Correto |
| slug | SlugField unique | ✅ Correto |
| cnpj | CharField | ⚠️ Sem validação de formato nem unique |
| deleted_at | DateTimeField null | ✅ Soft delete implementado |
| Indexes | slug, plan, deleted_at | ✅ + is_active+plan (migration 0009) |

**⚠️ Pendência:** CNPJ sem validação de formato (14 dígitos) e sem `unique=True`.  
**Recomendação:** Adicionar validador de CNPJ e `unique=True` se cada clínica terá 1 CNPJ.

---

### ✅ CustomUser (users)
| Campo | Tipo | Status |
|-------|------|--------|
| id (Django default) | BigAutoField | ✅ PK interna |
| uid | UUID unique | ✅ PK pública segura (não expõe ID sequencial) |
| email | EmailField unique | ✅ Correto |
| role | TextChoices (13 papéis) | ✅ Correto |
| deleted_at | DateTimeField null | ✅ Soft delete |
| Indexes | uid, role, email, deleted_at, org+role | ✅ Completo |

**✅ Padrão excelente:** Dual-ID (sequencial interno + UUID público), evita enumeração.

---

### ✅ PatientProfile (users)
| Campo | Tipo | Status |
|-------|------|--------|
| user | OneToOneField | ✅ Correto |
| cpf | CharField(14) | ⚠️ Sem unique + sem validação |
| blood_type | TextChoices | ✅ Correto |
| ai_summary | TextField | ✅ Pronto para integração IA |
| Indexes | cpf, risk_level, blood_type | ✅ Bom |

**⚠️ Pendência:** CPF sem validação e sem `unique=True`.  
**Recomendação:** CPF deve ser único por sistema de saúde.

---

### ✅ VerificationCode (users)
| Campo | Tipo | Status |
|-------|------|--------|
| code | CharField(6) | ✅ 6 dígitos |
| expires_at | DateTimeField | ✅ 10 minutos |
| is_used | BooleanField | ✅ Correto |
| Indexes | user+purpose+is_used, expires_at | ✅ (migration 0009) |

**✅ Padrão correto:** `generate()` invalida códigos anteriores automaticamente.

---

### ✅ PatientProfessionalAccess (users)
| Campo | Tipo | Status |
|-------|------|--------|
| unique_together | patient + professional | ✅ Correto |
| is_active + revoked_at | Soft revoke | ✅ Correto |
| granted_by | FK nullable | ✅ Correto |
| Indexes | patient+is_active, professional+is_active | ✅ Completo |

---

### ✅ AuditLog (users — LGPD art. 37)
| Campo | Tipo | Status |
|-------|------|--------|
| id | UUID PK | ✅ |
| actor | FK SET_NULL | ✅ Mantém log mesmo se user deletado |
| detail | JSONField | ✅ Flexível para metadados |
| Indexes | actor+timestamp, patient+timestamp, resource+timestamp, action+success, timestamp, resource_type+resource_id | ✅ Completo |

**✅ Excelente:** Log imutável por convenção, 6 índices cobrem todos os padrões de consulta.

---

### ✅ Consultation (consultations)
| Campo | Tipo | Status |
|-------|------|--------|
| id | UUID PK | ✅ |
| status | TextChoices (4) | ✅ |
| severity | TextChoices (4) | ✅ |
| icd_code | CharField(10) | ✅ CID-10 |
| ai_summary | TextField | ✅ Pronto para IA |
| Indexes | patient+date, org, status, severity, icd_code | ✅ Completo |

---

### ✅ VitalSign (consultations)
| Campo | Tipo | Status |
|-------|------|--------|
| patient | FK CASCADE | ✅ |
| date | DateField | ✅ |
| blood_pressure | CharField(20) | ⚠️ Sem validação de formato (ex: 120/80) |
| Indexes | patient+date (migration 0009) | ✅ Adicionado |

---

### ✅ ConsultationSession (consultations)
| Campo | Tipo | Status |
|-------|------|--------|
| token | UUID unique | ✅ Gerado automaticamente |
| status | TextChoices (4) | ⚠️ max_length=10 mas 'pending'=7 → OK |
| expires_at | DateTimeField | ✅ 24h por padrão |
| Indexes | status+expires_at, patient+status (migration 0009) | ✅ Adicionado |

---

### ✅ Evolution (consultations)
| Campo | Tipo | Status |
|-------|------|--------|
| professional | FK SET_NULL | ✅ Mantém evolução mesmo se profissional deletado |
| is_visible_to_patient | BooleanField | ✅ Controle de visibilidade |
| Indexes | consultation+category, professional | ✅ |

---

### ✅ Prescription (consultations)
| Campo | Tipo | Status |
|-------|------|--------|
| prescription_type | max_length=10 | ✅ 'pharmacy'=8 chars |
| Indexes | consultation+is_active, prescriber, prescription_type | ✅ |

---

### ✅ DiagnosisCID (consultations)
| Indexes | consultation, icd_code, consultation+is_primary | ✅ (0009 adicionou o 3º) |

---

### ✅ LabRequest (consultations)
| Campo | Tipo | Status |
|-------|------|--------|
| urgency | BooleanField | ✅ |
| status | max_length=10 | ⚠️ 'completed'=9, 'cancelled'=9 → OK |
| Indexes | consultation+status, requesting_professional, status, urgency+status | ✅ |

---

## Problemas Identificados e Corrigidos

| # | Problema | Model | Solução |
|---|---------|-------|---------|
| 1 | Index ausente `patient+date` | VitalSign | ✅ Migration 0009 |
| 2 | Index ausente `status+expires_at` | ConsultationSession | ✅ Migration 0009 |
| 3 | Index ausente `user+purpose+is_used` | VerificationCode | ✅ Migration 0009 |
| 4 | Index ausente `consultation+tab` | ConsultationImage | ✅ Migration 0009 |
| 5 | Index ausente `consultation+is_primary` | DiagnosisCID | ✅ Migration 0009 |
| 6 | Index ausente `urgency+status` | LabRequest | ✅ Migration 0009 |
| 7 | `python-decouple` faltando no requirements | config | ✅ Adicionado |
| 8 | .dockerignore incompleto | Docker | ✅ Expandido |

## Pendências Futuras (não críticas)

| # | Pendência | Prioridade |
|---|----------|-----------|
| 1 | Validar e tornar CPF único em PatientProfile | Média |
| 2 | Validar formato CNPJ em Organization | Baixa |
| 3 | Validar formato `blood_pressure` (regex: \d+/\d+) | Baixa |
| 4 | Arquivar AuditLog antigos (>2 anos) em tabela fria | Futura |
| 5 | Particionar tabela AuditLog por mês quando >1M registros | Futura |

---

## Avaliação de Escalabilidade

| Critério | Status | Observação |
|---------|--------|------------|
| UUID PKs | ✅ | Sem enumeração, seguro para API pública |
| Indexes compostos | ✅ | Cobrem todos os padrões de query conhecidos |
| Soft delete | ✅ | Organization + CustomUser |
| Connection pooling | ✅ | Configurado no settings.py (conn_max_age=600) |
| Multi-tenant | ✅ | Organization + OrganizationMember |
| LGPD | ✅ | AuditLog com 6 índices |
| IA ready | ✅ | ai_summary + ai_last_analysis nos models principais |
| Supabase SSL | ✅ | ssl_require=True em produção |

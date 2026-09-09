# Backlog técnico — LIDDIS

Itens abertos de prevenção e manutenção, em ordem de prioridade. Cada um traz o
critério que permite considerá-lo encerrado e o teste que sustenta esse critério.

Atualizado em 09/09/2026.

---

## Prioridade crítica

### C1 — Contas duplicadas pelo mesmo e-mail

**Problema.** O banco aceita duas contas com o mesmo e-mail em caixas diferentes
(`maria@x.com` e `MARIA@x.com`). O modelo não tem restrição case-insensitive.

**Impacto.** Até 09/09 o `pre_social_login` fazia `get(email__iexact=...)` e
quebrava com `MultipleObjectsReturned` — erro 500 no meio do OAuth. O adapter já
foi endurecido para escolher a conta mais antiga e seguir, mas a causa persiste:
o histórico clínico da pessoa fica repartido entre duas contas, e ela vê metade
das próprias consultas.

**Ação.** Restrição `UniqueConstraint` sobre `Lower('email')` em `CustomUser`,
com migration de consolidação para as duplicatas que já existirem.

**Critério de aceite.** Tentar criar segunda conta com o mesmo e-mail em qualquer
caixa falha na validação; nenhuma duplicata remanescente no banco.

**Teste.** Caso que tenta criar a duplicata e espera `IntegrityError`; consulta de
verificação que exige zero grupos com contagem maior que um.

---

### C2 — Lista de IPs do Cloudflare fixa no código

**Problema.** `config/middleware.py` traz `_CF_RANGES` escrito à mão. O Cloudflare
publica faixas novas periodicamente.

**Impacto.** Requisição legítima vinda de faixa recém-adicionada recebe **403**.
A falha é intermitente e depende do nó de borda que atendeu a pessoa, o que a
torna difícil de reproduzir e fácil de atribuir ao lugar errado — inclusive ao
login com Google.

**Ação.** Buscar as faixas de `https://api.cloudflare.com/client/v4/ips` em cache
diário, mantendo a lista atual como fallback quando a busca falhar.

**Critério de aceite.** Faixa ausente da lista fixa mas presente na oficial é
aceita; indisponibilidade da API do Cloudflare não derruba o site.

**Teste.** Requisição com IP de faixa nova aceita; com a busca falhando, o
fallback continua aceitando as faixas conhecidas.

---

### C3 — Notificação por e-mail acoplada a operações críticas

**Problema.** `EMAIL_BACKEND` aponta para SMTP do Gmail, síncrono, dentro do ciclo
da requisição.

**Impacto.** Foi a causa raiz da regressão do login Google: `connect()` do allauth
envia e-mail de notificação, o envio falhava, a exceção subia e o vínculo entre a
conta Google e o usuário nunca era gravado. O login "funcionava" naquela tentativa
e repetia o mesmo caminho frágil na seguinte, indefinidamente. O adapter já grava
o vínculo à parte, mas qualquer envio síncrono ainda soma latência do SMTP ao
tempo de resposta.

**Ação.** Mover envio de e-mail para fora do ciclo da requisição (fila ou tarefa
em background).

**Critério de aceite.** Provedor de e-mail indisponível não altera o resultado de
nenhum fluxo de autenticação nem de gravação de consulta.

**Teste.** Já coberto para o OAuth em `test_falha_ao_notificar_nao_impede_a_vinculacao`;
estender o mesmo padrão a cadastro e recuperação de senha.

---

### C4 — Sem alerta automático para erro recorrente

**Problema.** O `/health/` responde sob demanda e os logs registram falha de OAuth,
mas ninguém é avisado — alguém precisa ir olhar.

**Impacto.** Falha em fluxo crítico só é descoberta quando um usuário reclama, que
foi exatamente como o problema do login Google chegou nas duas vezes.

**Ação.** Alerta no Cloud Monitoring sobre a métrica de logs com `oauth_falha` e
`health_check_falhou`, disparando por e-mail acima de um limiar por hora. Avaliar
Sentry para captura de exceção com stack trace.

**Critério de aceite.** Aumento anormal de falha de login gera notificação em
até quinze minutos, sem intervenção humana.

**Teste.** Validação manual documentada — gerar falhas em ambiente de teste e
confirmar o recebimento do alerta.

---

## Prioridade alta

### A1 — Template `socialaccount/login.html` descarta parâmetros do allauth

**Problema.** O template customizado hardcoda `{% url 'google_login' %}` no
`action` do formulário, descartando `process`, `next` e `scope` que o allauth
passa no contexto.

**Impacto.** O fluxo de login funciona, mas vincular uma conta Google a um usuário
já autenticado (`process=connect`) e o redirecionamento pós-login para a página de
origem (`next`) se perdem silenciosamente.

**Ação.** Usar `{% provider_login_url provider.id process=process scope=scope %}`,
preservando o desenho visual atual.

**Critério de aceite.** `process=connect` vincula sem criar conta nova; `next`
leva a pessoa de volta à página de onde partiu.

**Teste.** Caso para cada um dos dois parâmetros.

---

### A2 — Duas esteiras de deploy no repositório

**Problema.** Convivem `.github/workflows/deploy.yml` (GitHub Actions, que publica
em todo push e é a esteira real) e `cloudbuild.yaml` (Cloud Build, disparo manual).

**Impacto.** Na auditoria de 09/09, olhar só o histórico do Cloud Build levou à
conclusão errada de que nada era publicado desde maio, e a quatro builds manuais
desnecessários que geraram revisões duplicadas do mesmo commit.

**Ação.** Documentar o GitHub Actions como esteira oficial no README e marcar o
`cloudbuild.yaml` como recurso de emergência, com comentário no topo do arquivo.

**Critério de aceite.** Está escrito no repositório qual esteira publica e como
conferir o resultado.

---

### A3 — Configuração depreciada do allauth

**Problema.** `SOCIALACCOUNT_EMAIL_REQUIRED` permanece no settings; na linha 65 do
allauth o controle migrou para `ACCOUNT_SIGNUP_FIELDS`, já presente.

**Impacto.** Nenhum hoje. Vira quebra silenciosa quando a chave for removida numa
atualização futura.

**Ação.** Remover a chave obsoleta após confirmar que o comportamento não muda.

**Critério de aceite.** Suíte de OAuth passa sem a chave.

---

## Prioridade média

### M1 — `ATOMIC_REQUESTS` desabilitado

Cada view administra a própria transação. As críticas já usam `transaction.atomic()`
corretamente, mas uma view nova pode esquecer e gravar pela metade. Avaliar habilitar
globalmente, revisando as views que fazem chamada externa dentro da requisição.

### M2 — `docs/fluxo-operacional.pdf` fora do versionamento

Binário de 201 KB que duplica o HTML já versionado. Decidir entre versionar ou
remover, evitando que fique indefinidamente como arquivo solto.

### M3 — Anexo em formato HEIC

Formato de foto de iPhone que navegador nenhum renderiza. Hoje exibe "Anexo
indisponível" graças ao tratamento de erro. Converter no upload ou recusar o
formato explicitamente, com mensagem clara.

---

## Checklist antes de cada deploy

Ordem pensada para falhar cedo e barato.

1. `python -m pytest tests/ consultations/tests_external_patient.py -q` — a suíte
   inteira passa, sem teste marcado como pulado que devesse rodar.
2. `python manage.py check --deploy` — sem apontamentos.
3. `python manage.py makemigrations --check --dry-run` — nenhuma migration
   pendente de gerar.
4. `git diff --cached` revisado — nenhum segredo, nenhum dado pessoal, nenhum
   arquivo temporário.
5. `git push` — o GitHub Actions publica sozinho em cerca de dois minutos.
6. `gh run list --limit 1` — a execução terminou com sucesso.
7. `curl https://liddis.com.br/health/` — responde `{"status": "ok"}`.
8. Teste prático no ar: entrar com Google, abrir uma consulta com anexo, salvar
   um atendimento. Build verde não substitui esta etapa.

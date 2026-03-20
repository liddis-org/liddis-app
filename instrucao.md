Você é um especialista em arquitetura de software, UX/UI design moderno e aplicações de saúde digitais com dados sensíveis. Preciso que você gere um **plano completo de arquitetura e design** para um projeto chamado "HealthData Hub", incluindo sugestões de tecnologia, fluxo de dados, módulos e interface visual, pensando tanto em **website moderno** quanto **futuro aplicativo mobile**.

**Contexto do Projeto:**
- Plataforma para gestão de dados de saúde dos pacientes.
- Consolida histórico médico de diferentes profissionais: médicos, nutricionistas, enfermeiros, fisioterapeutas.
- Permite upload de documentos, exames, receitas, sinais vitais, prescrições e anamnese.
- Pacientes podem gerar **tokens temporários** para compartilhar dados com profissionais.
- Profissionais acessam dados via token e recebem **resumos inteligentes de IA**, que destacam pontos críticos, alertas de condições pré-existentes e interações medicamentosas.
- Futuro: integração com sistemas de saúde públicos/privados, controles de segurança granulares por tipo de profissional.

**Tecnologias escolhidas:**
- Backend: Python + Django (monolito modular)
- Front-end: React (SPA para web) + futura opção de React Native para app
- Banco de dados: PostgreSQL (relacional)
- Armazenamento de documentos: S3 ou equivalente
- IA: inicialmente módulo interno em Django, futuramente microserviço FastAPI
- Segurança: JWT/OAuth2, TLS, criptografia no banco, roles de acesso

**Requisitos de Arquitetura:**
1. Modular e fácil de entender para desenvolvedores iniciantes.
2. API REST clara para comunicação front-end / backend / futuro app.
3. Módulos separados por domínio: `users`, `patients`, `professionals`, `consultations`, `reports`, `tokens`.
4. Fluxo de dados seguro e eficiente.
5. IA que processa dados dos pacientes e gera relatórios contextuais.
6. Armazenamento de documentos seguro e criptografado.
7. Autenticação robusta e controle de acesso granular.

**Design e UX/UI:**
- Moderno, limpo e eficiente.
- Dashboards claros e intuitivos para pacientes e profissionais.
- Upload de documentos simples e seguro.
- Visualização de histórico de consultas organizada em cards ou listas interativas.
- Painel de relatórios com gráficos, alertas e resumos gerados pela IA.
- Interfaces responsivas para web e mobile.

**Objetivo do Prompt:**
- Gerar um **plano de arquitetura completo**, incluindo diagramas de fluxo de dados.
- Sugerir **componentes visuais modernos** para web e app.
- Indicar padrões de segurança, escalabilidade e modularidade.
- Fornecer **opções modernas de UI/UX** para dashboards e telas de login, upload, histórico e relatórios.
- Mostrar como o sistema pode evoluir para microserviços no futuro sem quebrar a arquitetura inicial.

**Extras:**
- Sugira cores, estilos de interface e layout que sejam modernos e eficientes.
- Explique cada módulo da arquitetura e fluxo de dados de forma clara.
- Inclua recomendações de bibliotecas modernas de React para dashboards, formulários e gráficos.
- Indique opções de visualizações de dados relevantes para pacientes e profissionais de saúde.
- Crie também **uma visão simplificada da futura arquitetura mobile**, compartilhando API com a web.

Por favor, entregue **uma proposta completa**, incluindo:

1. Arquitetura geral do sistema com módulos, backend, frontend, IA e banco de dados.  
2. Fluxo de dados detalhado entre paciente, profissional, frontend, backend, IA e armazenamento.  
3. Layouts e componentes visuais recomendados para web e app.  
4. Sugestões de design moderno e eficiente, incluindo cores, dashboards, cards, gráficos e uploads.  
5. Recomendações futuras de escalabilidade e microserviços.
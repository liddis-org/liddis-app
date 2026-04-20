# 🩺 HDI – Health Data Integration

O **HDI** é um aplicativo de saúde que **integra os dados do paciente** e devolve essas
informações para quem realmente importa: **o próprio paciente**.

A plataforma conecta **pacientes** e **profissionais da saúde**, permitindo que os dados
clínicos sejam organizados, acessíveis e utilizados de forma simples e segura.

Este repositório contém o **backend do projeto**, desenvolvido em **Django**.

---

## 🎯 Visão do Produto

- Centralizar dados de saúde do paciente
- Facilitar o acesso às informações clínicas
- Dar protagonismo ao paciente sobre seus próprios dados
- Criar uma base sólida para integração com profissionais da saúde

---

## 🛠️ Tecnologias Utilizadas

- **Python 3.10+**
- **Django 5.x**
- **SQLite** (ambiente local)
- **Git / GitHub**

> Em ambientes futuros, o banco poderá ser migrado para PostgreSQL.

---

## 📂 Estrutura do Projeto

```text
hdi/
├── config/            # Configurações principais do Django
├── users/             # App de usuários (base para autenticação)
├── venv/              # Ambiente virtual (não versionado)
├── manage.py
├── requirements.txt
├── .gitignore
└── README.md


⚙️ Pré-requisitos

Antes de começar, verifique se você possui:

python --version
git --version


Requisitos:

Python 3.10 ou superior

Git instalado

(Opcional) VS Code

🚀 Rodando o Projeto Localmente (Passo a Passo)
1️⃣ Clonar o repositório
git clone https://github.com/devGabriel-oliveira/hdi.git
cd hdi

2️⃣ Criar o ambiente virtual
python -m venv venv

3️⃣ Ativar o ambiente virtual

Windows (PowerShell):

.\venv\Scripts\Activate.ps1


Se ocorrer erro de permissão:

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1


Linux / macOS:

source venv/bin/activate


Quando ativado, o terminal exibirá:

(venv)

4️⃣ Instalar as dependências
pip install -r requirements.txt

5️⃣ Aplicar as migrações do banco
python manage.py migrate

6️⃣ Criar um superusuário (opcional)
python manage.py createsuperuser

7️⃣ Rodar o servidor local
python manage.py runserver

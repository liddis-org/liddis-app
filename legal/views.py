"""
Exibição pública dos documentos jurídicos.

São páginas abertas por exigência do próprio documento: a pessoa precisa poder
ler os termos antes de criar conta, e o rodapé do site leva até aqui sem login.
"""
from django.conf import settings
from django.http import Http404
from django.shortcuts import render

from .models import TermsDocument


def _contexto_empresa():
    """Dados oficiais que preenchem os campos do documento."""
    empresa = dict(getattr(settings, 'EMPRESA', {}))
    return {'empresa': empresa}


def _render_documento(request, tipo, secao=None):
    documento = TermsDocument.vigente(tipo)
    if documento is None:
        raise Http404('Documento ainda não publicado.')

    contexto = _contexto_empresa()
    contexto.update({
        'documento': documento,
        'secao_ativa': secao,
        'outro_tipo': (TermsDocument.Tipo.PACIENTE
                       if tipo == TermsDocument.Tipo.PROFISSIONAL
                       else TermsDocument.Tipo.PROFISSIONAL),
    })
    return render(request, 'legal/documento.html', contexto)


def termos_profissional(request):
    return _render_documento(request, TermsDocument.Tipo.PROFISSIONAL)


def termos_paciente(request):
    return _render_documento(request, TermsDocument.Tipo.PACIENTE)


def termos(request):
    """
    Rota genérica, usada pelo rodapé e pelos links de cadastro.

    Leva ao documento do papel de quem está logado; para visitante não
    autenticado, ao do paciente, que é o público majoritário. Se o documento
    preferido ainda não estiver publicado, cai no outro em vez de responder
    404 — é rota pública citada no próprio contrato, e página inacessível de
    termos é problema de conformidade, não só de navegação.
    """
    role = getattr(request.user, 'role', None) if request.user.is_authenticated else None
    preferido = (TermsDocument.Tipo.PROFISSIONAL
                 if role and role != 'PATIENT'
                 else TermsDocument.Tipo.PACIENTE)
    alternativo = (TermsDocument.Tipo.PACIENTE
                   if preferido == TermsDocument.Tipo.PROFISSIONAL
                   else TermsDocument.Tipo.PROFISSIONAL)

    tipo = preferido if TermsDocument.vigente(preferido) else alternativo
    return _render_documento(request, tipo)

"""
Documentos jurídicos e registro de aceite.

O texto dos documentos vive em templates versionados pelo git — é lá que a
revisão de cláusula acontece, com histórico e diff. O banco guarda qual versão
está vigente e, principalmente, **qual versão cada pessoa aceitou**: sem isso
não é possível demonstrar, anos depois, a que termos alguém se vinculou.

Publicar uma versão nova não invalida os aceites anteriores nem apaga o
histórico; apenas troca a vigente, e quem aceitou a anterior passa a ter aceite
pendente para a nova.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class TermsDocument(models.Model):
    """Uma versão publicada de um documento jurídico."""

    class Tipo(models.TextChoices):
        PROFISSIONAL = 'professional', 'Termos do Profissional'
        PACIENTE     = 'patient',      'Termos do Paciente'

    tipo = models.CharField(
        max_length=20, choices=Tipo.choices, verbose_name='Tipo de documento',
    )
    versao = models.CharField(
        max_length=20, verbose_name='Versão',
        help_text='Ex.: 1.0. Toda alteração de cláusula exige versão nova.',
    )
    titulo = models.CharField(max_length=200, verbose_name='Título')
    template = models.CharField(
        max_length=200, verbose_name='Template',
        help_text='Caminho do template com o texto, ex.: legal/professional_v1_0.html',
    )
    vigente_desde = models.DateField(verbose_name='Vigente desde')
    exige_novo_aceite = models.BooleanField(
        default=True, verbose_name='Exige novo aceite',
        help_text='Desmarque em correções de forma que não alterem direitos e deveres.',
    )
    publicado = models.BooleanField(default=True, verbose_name='Publicado')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'legal_terms_document'
        verbose_name = 'Documento jurídico'
        verbose_name_plural = 'Documentos jurídicos'
        ordering = ['tipo', '-vigente_desde', '-versao']
        constraints = [
            models.UniqueConstraint(
                fields=['tipo', 'versao'], name='documento_versao_unica',
            ),
        ]

    def __str__(self):
        return f'{self.get_tipo_display()} v{self.versao}'

    @classmethod
    def vigente(cls, tipo):
        """
        Documento em vigor para o tipo, ou None quando nenhum foi publicado.

        Vigência é por data, não por flag: assim é possível cadastrar a próxima
        versão com antecedência — como exige a cláusula de aviso prévio de 30
        dias — sem que ela entre no ar antes do tempo.
        """
        return (cls.objects
                .filter(tipo=tipo, publicado=True, vigente_desde__lte=timezone.localdate())
                .order_by('-vigente_desde', '-criado_em')
                .first())

    @classmethod
    def para_papel(cls, role):
        """Documento aplicável ao papel do usuário."""
        tipo = cls.Tipo.PACIENTE if role == 'PATIENT' else cls.Tipo.PROFISSIONAL
        return cls.vigente(tipo)


class TermsAcceptance(models.Model):
    """
    Registro de que uma pessoa aceitou uma versão específica.

    Nunca é atualizado: cada aceite gera uma linha. O histórico completo é o
    que sustenta a prova em caso de questionamento.
    """

    class Origem(models.TextChoices):
        CADASTRO   = 'signup',  'Cadastro'
        REACEITE   = 'reaccept', 'Novo aceite de versão'
        OAUTH      = 'oauth',   'Cadastro via Google'

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='aceites_termos', verbose_name='Usuário',
    )
    documento = models.ForeignKey(
        TermsDocument, on_delete=models.PROTECT,
        related_name='aceites', verbose_name='Documento',
    )
    # Cópias do momento do aceite: o documento pode ser corrigido depois, e o
    # que vale como prova é o que estava valendo quando a pessoa clicou.
    tipo_documento = models.CharField(max_length=20, verbose_name='Tipo')
    versao = models.CharField(max_length=20, verbose_name='Versão aceita')
    papel = models.CharField(
        max_length=20, verbose_name='Papel na época',
        help_text='PATIENT, DOCTOR, NURSE etc. no momento do aceite.',
    )
    origem = models.CharField(
        max_length=20, choices=Origem.choices, default=Origem.CADASTRO,
        verbose_name='Origem do aceite',
    )
    aceito_em = models.DateTimeField(default=timezone.now, verbose_name='Data e hora')
    ip = models.GenericIPAddressField(null=True, blank=True, verbose_name='Endereço IP')
    user_agent = models.CharField(max_length=300, blank=True, verbose_name='Navegador')

    # Aceites adicionais previstos no Anexo A do documento profissional.
    declarou_habilitacao = models.BooleanField(
        default=False, verbose_name='Declarou habilitação profissional',
    )
    aceitou_marketing = models.BooleanField(
        default=False, verbose_name='Aceitou comunicações de marketing',
    )

    class Meta:
        db_table = 'legal_terms_acceptance'
        verbose_name = 'Aceite de termos'
        verbose_name_plural = 'Aceites de termos'
        ordering = ['-aceito_em']
        indexes = [
            models.Index(fields=['usuario', 'tipo_documento'], name='aceite_usuario_tipo_idx'),
        ]

    def __str__(self):
        return f'{self.usuario} aceitou {self.tipo_documento} v{self.versao}'

    @classmethod
    def registrar(cls, usuario, documento, request=None, origem=Origem.CADASTRO,
                  declarou_habilitacao=False, aceitou_marketing=False):
        """Grava o aceite com a evidência disponível na requisição."""
        ip, agente = None, ''
        if request is not None:
            from users.audit import _get_ip
            ip = _get_ip(request)
            agente = request.META.get('HTTP_USER_AGENT', '')[:300]

        return cls.objects.create(
            usuario=usuario,
            documento=documento,
            tipo_documento=documento.tipo,
            versao=documento.versao,
            papel=getattr(usuario, 'role', '') or '',
            origem=origem,
            ip=ip,
            user_agent=agente,
            declarou_habilitacao=declarou_habilitacao,
            aceitou_marketing=aceitou_marketing,
        )

    @classmethod
    def pendente_para(cls, usuario):
        """
        Documento que o usuário ainda precisa aceitar, ou None.

        Só considera pendente quando a versão vigente exige novo aceite —
        correção de forma não interrompe o uso da plataforma.
        """
        documento = TermsDocument.para_papel(getattr(usuario, 'role', ''))
        if documento is None or not documento.exige_novo_aceite:
            return None
        ja_aceitou = cls.objects.filter(
            usuario=usuario, tipo_documento=documento.tipo, versao=documento.versao,
        ).exists()
        return None if ja_aceitou else documento

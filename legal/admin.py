from django.contrib import admin

from .models import TermsAcceptance, TermsDocument


@admin.register(TermsDocument)
class TermsDocumentAdmin(admin.ModelAdmin):
    list_display  = ('tipo', 'versao', 'titulo', 'vigente_desde', 'publicado', 'exige_novo_aceite')
    list_filter   = ('tipo', 'publicado', 'exige_novo_aceite')
    search_fields = ('titulo', 'versao')
    ordering      = ('tipo', '-vigente_desde')


@admin.register(TermsAcceptance)
class TermsAcceptanceAdmin(admin.ModelAdmin):
    list_display     = ('usuario', 'tipo_documento', 'versao', 'papel', 'origem', 'aceito_em')
    list_filter      = ('tipo_documento', 'versao', 'papel', 'origem')
    search_fields    = ('usuario__email', 'usuario__username', 'versao')
    date_hierarchy   = 'aceito_em'
    ordering         = ('-aceito_em',)

    # O aceite é prova: não se edita nem se cria pela administração.
    readonly_fields = tuple(f.name for f in TermsAcceptance._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

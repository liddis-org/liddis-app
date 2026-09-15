"""
Publica a versão 1.0 dos Termos do Paciente.

Mesmo desenho da migration do documento profissional: o texto vive em template
versionado pelo git e aqui apenas se registra a versão vigente, para que os
aceites tenham a que apontar.
"""
from datetime import date

from django.db import migrations


def publicar(apps, schema_editor):
    TermsDocument = apps.get_model('legal', 'TermsDocument')
    TermsDocument.objects.get_or_create(
        tipo='patient',
        versao='1.0',
        defaults={
            'titulo': 'Termos de Uso e Política de Privacidade do Usuário',
            'template': 'legal/patient_v1_0.html',
            'vigente_desde': date(2026, 9, 15),
            'exige_novo_aceite': True,
            'publicado': True,
        },
    )


def despublicar(apps, schema_editor):
    TermsDocument = apps.get_model('legal', 'TermsDocument')
    # Não apaga: pode haver aceites apontando para esta versão (FK PROTECT).
    TermsDocument.objects.filter(tipo='patient', versao='1.0').update(publicado=False)


class Migration(migrations.Migration):

    dependencies = [('legal', '0002_seed_professional_v1')]

    operations = [migrations.RunPython(publicar, despublicar)]

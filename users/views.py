import json
import logging
import functools
import threading
from urllib.request import Request, urlopen
from urllib.error import URLError
from urllib.parse import quote
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.views import View
from django.http import HttpResponseForbidden

# API views (REST)
from rest_framework import generics, permissions
from .serializers import RegisterSerializer, UserSerializer
from .models import CustomUser, VerificationCode, PlatformFeedback
from .forms import RegisterForm, ProfileForm, PlatformFeedbackForm

logger = logging.getLogger('liddis')

# Roles profissionais (não-paciente)
PROFESSIONAL_ROLES = {
    'DOCTOR', 'NURSE', 'NUTRITIONIST', 'PHYSIO',
    'SPEECH_THERAPIST', 'PHYSICAL_EDUCATOR', 'PSYCHOLOGIST',
    'DENTIST', 'OCC_THERAPIST', 'PHARMACIST', 'ADMIN',
}


# ── RBAC Decorators ────────────────────────────────────────────────────────────

def require_role(*roles):
    """
    Decorator que restringe acesso a usuários com role específica.
    Uso: @require_role('DOCTOR', 'NURSE')
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.role not in roles:
                logger.warning(
                    'Acesso negado: user=%s role=%s tentou acessar view restrita a %s',
                    request.user.username, request.user.role, roles,
                )
                messages.error(request, 'Você não tem permissão para acessar esta área.')
                return redirect('dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_professional(view_func):
    """Atalho: restringe a qualquer role profissional (não-paciente)."""
    @functools.wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.role == 'PATIENT':
            messages.error(request, 'Esta área é exclusiva para profissionais de saúde.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def require_patient(view_func):
    """Atalho: restringe apenas a pacientes."""
    @functools.wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.role != 'PATIENT':
            messages.error(request, 'Esta área é exclusiva para pacientes.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


# ── Home ───────────────────────────────────────────────────────────────────────

def home(request):
    return render(request, 'home.html')


# ── WhatsApp ────────────────────────────────────────────────────────────────────

_PLANOS_WA = {
    'premium': {
        'nome': 'Premium / Pro',
        'msg':  'Olá! Tenho interesse no plano *Premium* da LIDDIS. Podem me ajudar?',
    },
    'professional': {
        'nome': 'Professional / Advanced',
        'msg':  'Olá! Tenho interesse no plano *Professional* da LIDDIS. Podem me ajudar?',
    },
    'enterprise': {
        'nome': 'Enterprise / Organization',
        'msg':  'Olá! Gostaria de falar sobre o plano *Enterprise* da LIDDIS. Quero falar com vendas.',
    },
}


def _notify_whatsapp_admin(plano_nome: str) -> None:
    """Notifica o admin via WhatsApp Business Cloud API (roda em background thread)."""
    token    = getattr(settings, 'WHATSAPP_API_TOKEN', '')
    phone_id = getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', '')
    admin    = getattr(settings, 'WHATSAPP_ADMIN_NUMBER', '')

    if not all([token, phone_id, admin]):
        return  # credenciais não configuradas — ignora silenciosamente

    body = json.dumps({
        'messaging_product': 'whatsapp',
        'to': admin,
        'type': 'text',
        'text': {
            'body': (
                f'🔔 *LIDDIS — Novo Interesse*\n\n'
                f'Um usuário clicou em *{plano_nome}*.\n'
                f'Entre em contato para fechar a venda! 🚀'
            )
        },
    }).encode()

    req = Request(
        f'https://graph.facebook.com/v18.0/{phone_id}/messages',
        data=body,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type':  'application/json',
        },
        method='POST',
    )
    try:
        with urlopen(req, timeout=5):
            logger.info('Admin notificado via WhatsApp: plano %s', plano_nome)
    except URLError as exc:
        logger.warning('Falha na notificação WhatsApp admin: %s', exc)


def whatsapp_redirect(request, plano):
    """Redireciona o usuário para o WhatsApp de vendas + notifica o admin em background."""
    cfg = _PLANOS_WA.get(plano)
    if not cfg:
        return redirect('landing')

    number = getattr(settings, 'WHATSAPP_SALES_NUMBER', '')
    if not number:
        logger.error('WHATSAPP_SALES_NUMBER não configurado no .env')
        return redirect('landing')

    # Dispara notificação ao admin sem bloquear o redirect do usuário
    threading.Thread(
        target=_notify_whatsapp_admin,
        args=(cfg['nome'],),
        daemon=True,
    ).start()

    wa_url = f"https://wa.me/{number}?text={quote(cfg['msg'])}"
    return redirect(wa_url)


# ── Helpers de envio ───────────────────────────────────────────────────────────

def _send_email_code(user):
    """
    Gera código OTP e envia e-mail HTML + texto puro.
    Em desenvolvimento (EMAIL_PROVIDER=console) imprime no terminal.
    Em produção envia via provedor configurado (Resend, SendGrid, Gmail...).
    """
    vc = VerificationCode.generate(user, purpose=VerificationCode.PURPOSE_EMAIL)
    ctx = {
        'first_name': user.first_name or user.username,
        'code':       vc.code,
        'channel':    'e-mail',
    }
    subject  = 'LIDDIS — Seu código de verificação'
    body_txt = render_to_string('email/otp.txt',  ctx)
    body_html = render_to_string('email/otp.html', ctx)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=body_txt,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    msg.attach_alternative(body_html, 'text/html')

    try:
        msg.send(fail_silently=False)
        logger.info('OTP e-mail enviado para %s', user.email)
    except Exception as exc:
        logger.error('Falha ao enviar OTP para %s: %s', user.email, exc)
        raise   # propaga para a view exibir mensagem de erro

    return vc


def _send_sms_code(user):
    """
    Gera código OTP e envia SMS via Twilio.
    Requer TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN e TWILIO_PHONE_NUMBER no .env.
    Retorna None silenciosamente se Twilio não estiver configurado ou instalado.
    """
    if not settings.SMS_ENABLED:
        logger.warning('SMS solicitado mas Twilio não configurado (SMS_ENABLED=False)')
        return None
    try:
        from twilio.rest import Client
        vc = VerificationCode.generate(user, purpose=VerificationCode.PURPOSE_PHONE)
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=f'LIDDIS: seu codigo de verificacao e {vc.code}. Valido por 10 minutos. Nao compartilhe.',
            from_=settings.TWILIO_PHONE_NUMBER,
            to=user.phone,
        )
        logger.info('OTP SMS enviado para %s', user.phone)
        return vc
    except ImportError:
        logger.error('Pacote twilio não instalado. Execute: pip install twilio')
        return None
    except Exception as exc:
        logger.error('Falha ao enviar SMS para %s: %s', user.phone, exc)
        return None


# ── API Views (para o futuro React frontend) ──────────────────────────────────

class RegisterAPIView(generics.CreateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


# ── Cadastro ───────────────────────────────────────────────────────────────────

class RegisterWebView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return render(request, 'users/already_logged.html')
        return render(request, 'users/register.html', {'form': RegisterForm()})

    def post(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend='users.backends.EmailOrUsernameBackend')
            try:
                _send_email_code(user)
                messages.info(request, f'Conta criada! Enviamos um código para {user.email}.')
            except Exception:
                messages.warning(
                    request,
                    f'Conta criada, mas não conseguimos enviar o e-mail para {user.email}. '
                    'Clique em "Reenviar código" na próxima tela.'
                )
            return redirect('verificar_email')
        return render(request, 'users/register.html', {'form': form})


# ── Verificação de E-mail ──────────────────────────────────────────────────────

@login_required
def verificar_email(request):
    user = request.user

    if user.is_email_verified:
        return redirect('dashboard')

    if request.method == 'POST':
        action = request.POST.get('action')

        # Reenviar código
        if action == 'reenviar':
            try:
                _send_email_code(user)
                messages.success(request, f'Novo código enviado para {user.email}.')
            except Exception:
                messages.error(request, 'Não foi possível enviar o e-mail agora. Tente novamente em alguns minutos.')
            return redirect('verificar_email')

        # Confirmar código
        code_input = request.POST.get('code', '').strip()
        vc = (
            VerificationCode.objects
            .filter(user=user, purpose=VerificationCode.PURPOSE_EMAIL, is_used=False)
            .order_by('-created_at')
            .first()
        )

        if not vc:
            messages.error(request, 'Nenhum código ativo. Clique em "Reenviar".')
        elif vc.is_expired:
            vc.is_used = True
            vc.save()
            messages.error(request, 'Código expirado. Clique em "Reenviar".')
        elif vc.code != code_input:
            messages.error(request, 'Código incorreto. Tente novamente.')
        else:
            vc.is_used = True
            vc.save()
            user.is_email_verified = True
            user.save(update_fields=['is_email_verified'])
            messages.success(request, 'E-mail verificado! Bem-vindo(a) ao LIDDIS.')
            return redirect('dashboard')

    return render(request, 'users/verificar_email.html', {'email': user.email})


# ── Verificação de Celular ─────────────────────────────────────────────────────

@login_required
def verificar_celular(request):
    user = request.user

    if user.is_phone_verified:
        return redirect('dashboard')

    if not user.phone:
        messages.warning(request, 'Cadastre seu celular no perfil primeiro.')
        return redirect('profile')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'reenviar':
            if not settings.SMS_ENABLED:
                messages.error(request, 'Envio de SMS não configurado ainda.')
                return redirect('verificar_celular')
            _send_sms_code(user)
            messages.success(request, f'Novo código enviado para {user.phone}.')
            return redirect('verificar_celular')

        code_input = request.POST.get('code', '').strip()
        vc = (
            VerificationCode.objects
            .filter(user=user, purpose=VerificationCode.PURPOSE_PHONE, is_used=False)
            .order_by('-created_at')
            .first()
        )

        if not vc:
            messages.error(request, 'Nenhum código ativo. Clique em "Reenviar".')
        elif vc.is_expired:
            vc.is_used = True
            vc.save()
            messages.error(request, 'Código expirado. Clique em "Reenviar".')
        elif vc.code != code_input:
            messages.error(request, 'Código incorreto. Tente novamente.')
        else:
            vc.is_used = True
            vc.save()
            user.is_phone_verified = True
            user.save(update_fields=['is_phone_verified'])
            messages.success(request, 'Celular verificado com sucesso!')
            return redirect('profile')

    return render(request, 'users/verificar_celular.html', {
        'phone': user.phone,
        'sms_enabled': settings.SMS_ENABLED,
    })


# ── Dashboard (Início) ─────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    from consultations.models import Consultation, VitalSign

    is_professional = request.user.role != 'PATIENT'

    if is_professional:
        try:
            atendimentos = list(
                Consultation.objects.filter(session__professional=request.user).order_by('-date')
            )
            ultimo = atendimentos[0] if atendimentos else None
            return render(request, 'dashboard.html', {
                'is_professional': True,
                'total_atendimentos': len(atendimentos),
                'ultimo_atendimento': ultimo.date if ultimo else None,
                'atendimentos_recentes': atendimentos[:5],
            })
        except Exception as exc:
            logger.error('Erro ao carregar dashboard profissional: %s', exc)
            messages.error(request, 'Não foi possível carregar os dados. Tente novamente.')
            return render(request, 'dashboard.html', {
                'is_professional': True,
                'total_atendimentos': 0,
                'ultimo_atendimento': None,
                'atendimentos_recentes': [],
            })

    try:
        consultations = list(
            Consultation.objects.filter(patient=request.user).order_by('-date')[:5]
        )
        vitals = list(VitalSign.objects.filter(patient=request.user).order_by('-date')[:1])
        total  = Consultation.objects.filter(patient=request.user).count()
    except Exception as exc:
        logger.error('Erro ao carregar dashboard paciente: %s', exc)
        messages.error(request, 'Não foi possível carregar os dados. Tente novamente.')
        consultations, vitals, total = [], [], 0

    return render(request, 'dashboard.html', {
        'is_professional': False,
        'consultations':   consultations,
        'latest_vital':    vitals[0] if vitals else None,
        'total_consultations': total,
    })


# ── Analytics Dashboard ────────────────────────────────────────────────────────

@login_required
def analytics(request):
    import json
    from datetime import date
    from django.db.models import Count
    from django.db.models.functions import TruncMonth
    from consultations.models import Consultation, VitalSign, SPECIALTY_CHOICES

    is_professional = request.user.role != 'PATIENT'
    today = date.today()
    SPECIALTY_MAP = dict(SPECIALTY_CHOICES)
    SEVERITY_MAP  = {'low': 'Leve', 'moderate': 'Moderada', 'high': 'Grave', 'critical': 'Crítica'}

    # 12-month sequence (chronological)
    months_seq = []
    for i in range(11, -1, -1):
        m = today.month - i
        y = today.year
        if m <= 0:
            m += 12
            y -= 1
        months_seq.append(date(y, m, 1))

    month_labels = [d.strftime('%b/%y') for d in months_seq]
    month_keys   = [d.strftime('%Y-%m') for d in months_seq]

    def monthly_values(qs):
        raw = (
            qs.annotate(month=TruncMonth('date'))
            .values('month').annotate(count=Count('id'))
        )
        d = {item['month'].strftime('%Y-%m'): item['count'] for item in raw}
        return [d.get(k, 0) for k in month_keys]

    if is_professional:
        try:
            qs = Consultation.objects.filter(session__professional=request.user)
            total  = qs.count()
            ultimo = qs.order_by('-date').first()

            spec_raw = qs.values('specialty').annotate(count=Count('id')).order_by('-count')[:8]
            sev_raw  = qs.exclude(severity='').values('severity').annotate(count=Count('id'))

            this_month        = qs.filter(date__year=today.year, date__month=today.month).count()
            distinct_patients = qs.values('patient').distinct().count()

            return render(request, 'analytics.html', {
                'is_professional':    True,
                'total_atendimentos': total,
                'this_month':         this_month,
                'distinct_patients':  distinct_patients,
                'ultimo_atendimento': ultimo.date if ultimo else None,
                'atendimentos_recentes': list(qs.order_by('-date')[:5]),
                'chart_months':           json.dumps(month_labels),
                'chart_monthly':          json.dumps(monthly_values(qs)),
                'chart_specialty_labels': json.dumps([SPECIALTY_MAP.get(s['specialty'], s['specialty']) for s in spec_raw]),
                'chart_specialty_values': json.dumps([s['count'] for s in spec_raw]),
                'chart_severity_labels':  json.dumps([SEVERITY_MAP.get(s['severity'], s['severity']) for s in sev_raw]),
                'chart_severity_values':  json.dumps([s['count'] for s in sev_raw]),
            })
        except Exception as exc:
            logger.error('Erro ao carregar analytics profissional: %s', exc)
            messages.error(request, 'Não foi possível carregar os dados. Tente novamente.')
            return render(request, 'analytics.html', {
                'is_professional': True,
                'total_atendimentos': 0, 'this_month': 0,
                'distinct_patients': 0, 'ultimo_atendimento': None,
                'atendimentos_recentes': [],
                'chart_months': json.dumps(month_labels),
                'chart_monthly': json.dumps([0] * 12),
                'chart_specialty_labels': json.dumps([]),
                'chart_specialty_values': json.dumps([]),
                'chart_severity_labels':  json.dumps([]),
                'chart_severity_values':  json.dumps([]),
            })

    # ── Paciente ────────────────────────────────────────────────────────────────
    try:
        qs    = Consultation.objects.filter(patient=request.user)
        total = qs.count()

        spec_raw  = qs.values('specialty').annotate(count=Count('id')).order_by('-count')[:8]
        vitals_qs = list(VitalSign.objects.filter(patient=request.user).order_by('date')[:12])
        latest_vital = VitalSign.objects.filter(patient=request.user).order_by('-date').first()

        this_month        = qs.filter(date__year=today.year, date__month=today.month).count()
        specialties_count = qs.values('specialty').distinct().count()

        return render(request, 'analytics.html', {
            'is_professional':  False,
            'consultations':    list(qs.order_by('-date')[:5]),
            'latest_vital':     latest_vital,
            'total_consultations': total,
            'this_month':       this_month,
            'specialties_count': specialties_count,
            'chart_months':           json.dumps(month_labels),
            'chart_monthly':          json.dumps(monthly_values(qs)),
            'chart_specialty_labels': json.dumps([SPECIALTY_MAP.get(s['specialty'], s['specialty']) for s in spec_raw]),
            'chart_specialty_values': json.dumps([s['count'] for s in spec_raw]),
            'chart_vitals_dates':  json.dumps([v.date.strftime('%d/%m') for v in vitals_qs]),
            'chart_vitals_weight': json.dumps([float(v.weight) if v.weight else None for v in vitals_qs]),
            'chart_vitals_hr':     json.dumps([v.heart_rate for v in vitals_qs]),
            'chart_vitals_o2':     json.dumps([v.oxygen_saturation for v in vitals_qs]),
        })
    except Exception as exc:
        logger.error('Erro ao carregar analytics paciente: %s', exc)
        messages.error(request, 'Não foi possível carregar os dados. Tente novamente.')
        return render(request, 'analytics.html', {
            'is_professional': False,
            'consultations': [], 'latest_vital': None,
            'total_consultations': 0, 'this_month': 0, 'specialties_count': 0,
            'chart_months': json.dumps(month_labels),
            'chart_monthly': json.dumps([0] * 12),
            'chart_specialty_labels': json.dumps([]),
            'chart_specialty_values': json.dumps([]),
            'chart_vitals_dates':  json.dumps([]),
            'chart_vitals_weight': json.dumps([]),
            'chart_vitals_hr':     json.dumps([]),
            'chart_vitals_o2':     json.dumps([]),
        })


# ── Perfil ─────────────────────────────────────────────────────────────────────

@login_required
def profile(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Perfil atualizado com sucesso!')
            return redirect('profile')
    else:
        form = ProfileForm(instance=request.user)
    return render(request, 'users/profile.html', {'form': form})


def quem_somos(request):
    return render(request, 'quem_somos.html')


# ── Gestão de Vínculos Paciente-Profissional ───────────────────────────────────

@login_required
def my_accesses(request):
    """
    Paciente: visualiza e revoga vínculos com profissionais.
    Profissional: visualiza seus pacientes vinculados.
    """
    from .models import PatientProfessionalAccess

    user = request.user

    if user.role == 'PATIENT':
        accesses = PatientProfessionalAccess.objects.filter(
            patient=user
        ).select_related('professional').order_by('-granted_at')
        return render(request, 'users/my_accesses.html', {
            'accesses': accesses,
            'is_patient': True,
        })

    # Profissional
    accesses = PatientProfessionalAccess.objects.filter(
        professional=user, is_active=True
    ).select_related('patient').order_by('-granted_at')
    return render(request, 'users/my_accesses.html', {
        'accesses': accesses,
        'is_patient': False,
    })


@login_required
def grant_access(request):
    """Paciente concede acesso explícito a um profissional pelo e-mail."""
    if request.user.role != 'PATIENT':
        messages.error(request, 'Apenas pacientes podem conceder vínculos.')
        return redirect('my_accesses')

    from .models import PatientProfessionalAccess

    if request.method == 'POST':
        email  = request.POST.get('professional_email', '').strip().lower()
        reason = request.POST.get('reason', '').strip()[:200]

        try:
            professional = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            messages.error(request, f'Profissional com e-mail "{email}" não encontrado.')
            return redirect('my_accesses')

        if professional.role == 'PATIENT':
            messages.error(request, 'O e-mail informado pertence a um paciente, não a um profissional.')
            return redirect('my_accesses')

        obj, created = PatientProfessionalAccess.objects.get_or_create(
            patient=request.user,
            professional=professional,
            defaults={'granted_by': request.user, 'access_reason': reason, 'is_active': True},
        )
        if not created:
            if obj.is_active:
                messages.info(request, f'{professional.get_full_name() or professional.email} já tem acesso.')
            else:
                obj.is_active   = True
                obj.revoked_at  = None
                obj.access_reason = reason
                obj.save(update_fields=['is_active', 'revoked_at', 'access_reason'])
                messages.success(request, f'Acesso reativado para {professional.get_full_name() or professional.email}.')
        else:
            messages.success(request, f'Acesso concedido a {professional.get_full_name() or professional.email}.')

        from users.audit import log_access as audit
        audit(request, 'create', 'patient_professional_access',
              resource_id=obj.pk, patient=request.user)

    return redirect('my_accesses')


@login_required
def revoke_access(request, access_id):
    """Paciente revoga vínculo com um profissional."""
    import uuid
    from .models import PatientProfessionalAccess

    if request.user.role != 'PATIENT':
        messages.error(request, 'Apenas pacientes podem revogar vínculos.')
        return redirect('my_accesses')

    try:
        obj = PatientProfessionalAccess.objects.get(
            id=access_id, patient=request.user, is_active=True
        )
    except PatientProfessionalAccess.DoesNotExist:
        messages.error(request, 'Vínculo não encontrado.')
        return redirect('my_accesses')

    obj.revoke()
    from users.audit import log_access as audit
    audit(request, 'delete', 'patient_professional_access',
          resource_id=obj.pk, patient=request.user)
    messages.success(request, f'Acesso de {obj.professional.get_full_name() or obj.professional.email} revogado.')
    return redirect('my_accesses')


# ── Feedback da Plataforma ─────────────────────────────────────────────────────

@login_required
def platform_feedback(request):
    """Central de Feedback — pacientes e profissionais avaliam a plataforma."""
    if request.method == 'POST':
        form = PlatformFeedbackForm(request.POST)
        if form.is_valid():
            fb = form.save(commit=False)
            fb.user = request.user
            fb.role_at_time = request.user.role
            fb.save()
            messages.success(request, 'Obrigado pelo seu feedback! Sua avaliação foi registrada.')
            return redirect('platform_feedback')
    else:
        form = PlatformFeedbackForm()

    # Feedback anterior do usuário (último)
    ultimo_feedback = PlatformFeedback.objects.filter(user=request.user).order_by('-created_at').first()

    return render(request, 'users/feedback.html', {
        'form': form,
        'ultimo_feedback': ultimo_feedback,
    })

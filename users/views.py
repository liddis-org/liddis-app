import logging
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.views import View

# API views (REST)
from rest_framework import generics, permissions
from .serializers import RegisterSerializer, UserSerializer
from .models import CustomUser, VerificationCode
from .forms import RegisterForm, ProfileForm

logger = logging.getLogger('liddis')


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
            login(request, user, backend='axes.backends.AxesStandaloneBackend')
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
            _send_email_code(user)
            messages.success(request, f'Novo código enviado para {user.email}.')
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


# ── Dashboard ──────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    from consultations.models import Consultation, VitalSign

    is_professional = request.user.role != 'PATIENT'

    if is_professional:
        atendimentos = Consultation.objects.filter(
            session__professional=request.user
        ).order_by('-date')
        ultimo = atendimentos.first()
        return render(request, 'dashboard.html', {
            'is_professional': True,
            'total_atendimentos': atendimentos.count(),
            'ultimo_atendimento': ultimo.date if ultimo else None,
            'atendimentos_recentes': atendimentos[:5],
        })

    consultations = Consultation.objects.filter(patient=request.user).order_by('-date')[:5]
    vitals = VitalSign.objects.filter(patient=request.user).order_by('-date')[:1]
    total = Consultation.objects.filter(patient=request.user).count()
    return render(request, 'dashboard.html', {
        'is_professional': False,
        'consultations': consultations,
        'latest_vital': vitals.first(),
        'total_consultations': total,
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

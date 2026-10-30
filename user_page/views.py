import secrets
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.views.decorators.http import require_POST, require_GET
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from urllib.parse import urlencode
from django.db import IntegrityError, transaction

from saling_tebeng.models import RideBooking
from django_cas_ng.utils import get_cas_client

from .forms import ProfileForm, SaLinkAuthenticationForm, SignUpForm
from .models import SSOIdentity


def module_login(request):
    module_root = request.path.rsplit('login/', 1)[0]
    next_path = request.GET.get('next') or module_root
    if not url_has_allowed_host_and_scheme(
        next_path,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_path = module_root
    return redirect(f"{reverse('user_page:login')}?{urlencode({'next': next_path})}")


def _safe_next_url(request):
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return reverse('user_page:profile')


class SaLinkLoginView(LoginView):
    template_name = 'user_page/login.html'
    form_class = SaLinkAuthenticationForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_nav'] = 'login'
        next_path = self.request.GET.get('next') or self.request.POST.get('next', '')
        module_paths = (
            ('/saling-beli/', 'Saling Beli'),
            ('/saling-pinjam/', 'Saling Pinjam'),
            ('/saling-bagi/', 'Saling Bagi'),
            ('/saling-nebeng/', 'Saling Nebeng'),
            ('/saling-tebeng/', 'Saling Nebeng'),
            ('/nebeng/', 'Saling Nebeng'),
        )
        context['module_name'] = next(
            (name for prefix, name in module_paths if next_path.startswith(prefix)),
            'SaLink',
        )
        return context


def register(request):
    if request.user.is_authenticated:
        return redirect(_safe_next_url(request))

    form = SignUpForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, 'Akun SaLink berhasil dibuat. Selamat datang!')
        return redirect(_safe_next_url(request))

    return render(request, 'user_page/register.html', {
        'form': form,
        'next': request.GET.get('next') or request.POST.get('next', ''),
        'active_nav': 'register',
    })


@login_required
def profile(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profil berhasil diperbarui.')
            return redirect('user_page:profile')
    else:
        form = ProfileForm(instance=request.user)

    user = request.user
    from saling_beli.models import TransactionOrder
    transaction_count = TransactionOrder.objects.filter(
        Q(seller=user) | Q(buyer=user),
    ).exclude(stage=TransactionOrder.Stage.BATAL).count()
    ride_count = RideBooking.objects.filter(
        ride_schedule__ride_offer__driver=user,
    ).exclude(
        Q(passenger=user) | Q(status='cancelled'),
    ).count()
    stats = [
        {
            'label': 'Saling Beli',
            'value': user.item_listings.count(),
            'detail': f'{transaction_count} transaksi',
            'url': reverse('saling_beli:index'),
            'tone': 'gold',
        },
        {
            'label': 'Saling Pinjam',
            'value': user.borrow_requests.count(),
            'detail': f'{user.borrow_items.count()} barang ditawarkan',
            'url': reverse('saling_pinjam:my_borrows'),
            'tone': 'green',
        },
        {
            'label': 'Saling Bagi',
            'value': user.makanan_dibagikan.count(),
            'detail': 'makanan dibagikan',
            'url': reverse('saling_bagi:index'),
            'tone': 'orange',
        },
        {
            'label': 'Saling Nebeng',
            'value': ride_count,
            'detail': 'orang pernah ditebengi',
            'url': reverse('saling_tebeng:index'),
            'tone': 'beige',
        }
    ]
    return render(request, 'user_page/profile.html', {
        'form': form,
        'stats': stats,
    })


@login_required
@require_POST
def delete_account(request):
    user = request.user
    username = user.username
    logout(request)
    user.delete()
    messages.success(request, f'Akun @{username} telah berhasil dihapus. Username sekarang tersedia kembali untuk digunakan.')
    return redirect('user_page:login')


def _start_sso_flow(request, mode, next_url=None):
    """
    Memulai proses autentikasi UI SSO.
    State disimpan di session untuk menghubungkan callback
    dengan proses login atau linking yang dimulai pengguna.
    """
    state = secrets.token_urlsafe(32)

    flows = request.session.get('ui_sso_flows', {})
    flows[state] = {
        'mode': mode,
        'user_id': str(request.user.pk) if mode == 'link' else None,
        'next': next_url or reverse('user_page:profile'),
    }

    # Batasi jumlah flow yang tersimpan dalam session.
    while len(flows) > 5:
        flows.pop(next(iter(flows)))

    request.session['ui_sso_flows'] = flows

    callback_url = request.build_absolute_uri(
        reverse('user_page:sso_callback')
    )
    service_url = f'{callback_url}?{urlencode({"state": state})}'

    client = get_cas_client(
        service_url=service_url,
        request=request,
    )

    return redirect(client.get_login_url())


@require_GET
def sso_login(request):
    """
    Memulai login UI SSO untuk pengguna yang sudah
    menghubungkan identitas SSO dengan akun SaLink.
    """
    if request.user.is_authenticated:
        return redirect('user_page:profile')

    next_url = request.GET.get('next') or reverse('user_page:profile')

    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = reverse('user_page:profile')

    return _start_sso_flow(request, 'login', next_url)


@login_required
@require_GET
def sso_link(request):
    """
    Memulai proses linking UI SSO dengan akun SaLink
    yang sedang login.
    """
    return _start_sso_flow(request, 'link')


@require_GET
def sso_callback(request):
    """
    Memvalidasi CAS ticket dan menyelesaikan proses
    login atau linking akun SaLink.
    """
    ticket = request.GET.get('ticket')
    state = request.GET.get('state')

    flows = request.session.get('ui_sso_flows', {})
    flow = flows.pop(state, None) if state else None

    request.session['ui_sso_flows'] = flows

    if not ticket or not flow:
        messages.error(
            request,
            'Proses UI SSO tidak valid atau sudah kedaluwarsa. Silakan coba lagi.',
        )
        return redirect('user_page:login')

    callback_url = request.build_absolute_uri(
        reverse('user_page:sso_callback')
    )
    service_url = f'{callback_url}?{urlencode({"state": state})}'

    try:
        client = get_cas_client(
            service_url=service_url,
            request=request,
        )

        username, attributes, pgtiou = client.verify_ticket(ticket)

        if not username:
            raise ValueError('CAS tidak mengembalikan username.')

    except Exception:
        messages.error(
            request,
            'Verifikasi UI SSO gagal. Silakan coba beberapa saat lagi.',
        )
        return redirect('user_page:login')

    subject = str(username).strip()

    if not subject:
        messages.error(request, 'Identitas UI SSO tidak valid.')
        return redirect('user_page:login')

    # PROSES LINKING
    if flow['mode'] == 'link':
        if (
            not request.user.is_authenticated
            or str(request.user.pk) != flow['user_id']
        ):
            messages.error(
                request,
                'Sesi akun SaLink berubah. Silakan login kembali sebelum menghubungkan UI SSO.',
            )
            return redirect('user_page:login')

        user = request.user

        existing_identity = SSOIdentity.objects.filter(
            provider='ui',
            subject=subject,
        ).first()

        if existing_identity and existing_identity.user_id != user.pk:
            messages.error(
                request,
                'Identitas UI SSO tersebut sudah terhubung ke akun SaLink lain.',
            )
            return redirect('user_page:profile')

        user_identity = SSOIdentity.objects.filter(
            user=user,
        ).first()

        if user_identity and user_identity.subject != subject:
            messages.error(
                request,
                'Akun SaLink ini sudah terhubung dengan identitas UI SSO lain.',
            )
            return redirect('user_page:profile')

        if user_identity:
            messages.info(
                request,
                'Identitas UI SSO sudah terhubung dengan akun ini.',
            )
            return redirect('user_page:profile')

        try:
            with transaction.atomic():
                SSOIdentity.objects.create(
                    user=user,
                    provider='ui',
                    subject=subject,
                )
        except IntegrityError:
            messages.error(
                request,
                'Identitas UI SSO gagal dihubungkan karena sudah digunakan.',
            )
            return redirect('user_page:profile')

        messages.success(
            request,
            'Akun UI SSO berhasil dihubungkan dengan akun SaLink!',
        )
        return redirect('user_page:profile')

    # PROSES LOGIN
    if flow['mode'] == 'login':
        identity = SSOIdentity.objects.select_related('user').filter(
            provider='ui',
            subject=subject,
        ).first()

        if not identity:
            messages.warning(
                request,
                'Identitas UI SSO belum terhubung. Silakan login menggunakan akun SaLink terlebih dahulu untuk menghubungkannya.',
            )
            return redirect('user_page:login')

        user = identity.user

        if not user.is_active:
            messages.error(
                request,
                'Akun SaLink ini tidak aktif.',
            )
            return redirect('user_page:login')

        login(
            request,
            user,
            backend='django.contrib.auth.backends.ModelBackend',
        )

        next_url = flow.get('next') or reverse('user_page:profile')

        if not url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            next_url = reverse('user_page:profile')

        messages.success(
            request,
            'Berhasil login menggunakan UI SSO. Selamat datang kembali!',
        )
        return redirect(next_url)

    messages.error(request, 'Jenis autentikasi UI SSO tidak dikenali.')
    return redirect('user_page:login')


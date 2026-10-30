from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.views.decorators.http import require_POST
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from urllib.parse import urlencode

from saling_tebeng.models import RideBooking

from .forms import ProfileForm, SaLinkAuthenticationForm, SignUpForm


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
            ('/saling-tebeng/', 'Saling Tebeng'),
            ('/nebeng/', 'Saling Tebeng'),
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

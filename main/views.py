from django.core.cache import cache
from django.shortcuts import render
from saling_beli.models import ItemListing
from saling_bagi.models import Makanan
from saling_pinjam.models import BorrowItem
from saling_tebeng.models import RideSchedule

from SaLink.cache_keys import HOME


def show_main(request):
    public_data = cache.get(HOME)
    if public_data is None:
        public_data = {
            'featured_beli': list(ItemListing.objects.filter(status=ItemListing.Status.AVAILABLE).order_by('-created_at')[:4]),
            'latest_bagi': list(Makanan.objects.filter(is_available=True)[:3]),
            'borrow_items': list(BorrowItem.objects.filter(status='AVAILABLE')[:3]),
            'count_beli': ItemListing.objects.filter(status=ItemListing.Status.AVAILABLE).count(),
            'count_bagi': Makanan.objects.count(),
            'count_pinjam': BorrowItem.objects.count(),
            'count_tebeng': RideSchedule.objects.filter(
                is_active=True,
                ride_offer__is_active=True,
            ).count(),
        }
        cache.set(HOME, public_data, timeout=60)

    context = {
        **public_data,
    }
    return render(request, "index.html", context)


def panduan_cod(request):
    """Halaman panduan keselamatan transaksi Cash on Delivery (COD) di area kampus."""
    return render(request, "panduan_cod.html")


def faq(request):
    """Halaman Frequently Asked Questions (FAQ) & Syarat Ketentuan SaLink."""
    return render(request, "faq.html")

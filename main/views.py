from django.core.cache import cache
from django.shortcuts import render
from saling_beli.models import ItemListing
from saling_bagi.models import Makanan
from saling_pinjam.models import BorrowItem

from SaLink.cache_keys import HOME

def show_main(request):
    public_data = cache.get(HOME)
    if public_data is None:
        public_data = {
            'featured_beli': list(ItemListing.objects.all()[:4]),
            'latest_bagi': list(Makanan.objects.filter(is_available=True)[:3]),
            'borrow_items': list(BorrowItem.objects.filter(status='AVAILABLE')[:3]),
            'count_beli': ItemListing.objects.count(),
            'count_bagi': Makanan.objects.count(),
            'count_pinjam': BorrowItem.objects.count(),
        }
        cache.set(HOME, public_data, timeout=60)

    context = {
        **public_data,
    }
    return render(request, "index.html", context)


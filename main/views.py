from django.shortcuts import render
from saling_beli.models import ItemListing
from saling_bagi.models import Makanan
from saling_pinjam.models import BorrowItem

def show_main(request):
    featured_beli = ItemListing.objects.all()[:4]
    latest_bagi = Makanan.objects.filter(is_available=True)[:3]
    borrow_items = BorrowItem.objects.filter(status='AVAILABLE')[:3]

    context = {
        'featured_beli': featured_beli,
        'latest_bagi': latest_bagi,
        'borrow_items': borrow_items,
        'count_beli': ItemListing.objects.count(),
        'count_bagi': Makanan.objects.count(),
        'count_pinjam': BorrowItem.objects.count(),
    }
    return render(request, "index.html", context)

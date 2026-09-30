from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import BorrowItem, BorrowRequest
from .forms import BorrowItemForm, BorrowRequestForm

def item_list(request):
    """
    Katalog barang yang tersedia untuk dipinjam beserta filter pencarian dan kategori.
    """
    category = request.GET.get('category', '')
    query = request.GET.get('q', '')

    items = BorrowItem.objects.all()

    if category:
        items = items.filter(category=category)
    if query:
        items = items.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(pickup_location__icontains=query)
        )

    context = {
        'items': items,
        'categories': BorrowItem.Category.choices,
        'selected_category': category,
        'query': query,
    }
    return render(request, 'saling_pinjam/item_list.html', context)


def item_detail(request, id):
    """
    Detail barang pinjaman dan form pengajuan pinjam.
    """
    item = get_object_or_404(BorrowItem, id=id)
    request_form = BorrowRequestForm()

    context = {
        'item': item,
        'request_form': request_form,
    }
    return render(request, 'saling_pinjam/item_detail.html', context)


@login_required
def item_create(request):
    """
    Menambahkan barang baru yang ingin dipinjamkan ke mahasiswa lain.
    """
    if request.method == 'POST':
        form = BorrowItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.owner = request.user
            item.save()
            messages.success(request, f'Barang "{item.name}" berhasil didaftarkan untuk dipinjamkan!')
            return redirect('saling_pinjam:item_detail', id=item.id)
    else:
        form = BorrowItemForm()

    return render(request, 'saling_pinjam/item_form.html', {'form': form, 'title': 'Pinjamkan Barang Anda'})


@login_required
def request_borrow(request, id):
    """
    Mengajukan permohonan pinjam atas suatu barang.
    """
    item = get_object_or_404(BorrowItem, id=id)

    if item.owner == request.user:
        messages.error(request, 'Anda tidak bisa meminjam barang milik Anda sendiri.')
        return redirect('saling_pinjam:item_detail', id=item.id)

    if item.status != BorrowItem.Status.AVAILABLE:
        messages.warning(request, 'Maaf, barang ini sedang tidak tersedia untuk dipinjam.')
        return redirect('saling_pinjam:item_detail', id=item.id)

    if request.method == 'POST':
        form = BorrowRequestForm(request.POST)
        if form.is_valid():
            borrow_req = form.save(commit=False)
            borrow_req.item = item
            borrow_req.borrower = request.user
            borrow_req.save()
            messages.success(request, f'Pengajuan peminjaman "{item.name}" berhasil dikirim! Menunggu konfirmasi pemilik.')
            return redirect('saling_pinjam:my_borrows')
    else:
        form = BorrowRequestForm()

    return render(request, 'saling_pinjam/request_form.html', {'item': item, 'form': form})


@login_required
def my_borrows(request):
    """
    Dashboard untuk melihat:
    1. Pengajuan yang diajukan oleh user (sebagai peminjam)
    2. Pengajuan yang masuk atas barang-barang milik user (sebagai pemilik)
    """
    as_borrower = BorrowRequest.objects.filter(borrower=request.user).select_related('item', 'item__owner')
    as_owner = BorrowRequest.objects.filter(item__owner=request.user).select_related('item', 'borrower')
    my_items = BorrowItem.objects.filter(owner=request.user)

    context = {
        'as_borrower': as_borrower,
        'as_owner': as_owner,
        'my_items': my_items,
    }
    return render(request, 'saling_pinjam/my_borrows.html', context)


@login_required
def update_request_status(request, request_id, new_status):
    """
    Aksi persetujuan (Approve/Reject/Return) oleh pemilik barang.
    """
    borrow_req = get_object_or_404(BorrowRequest, id=request_id, item__owner=request.user)

    if new_status in [choice[0] for choice in BorrowRequest.Status.choices]:
        borrow_req.status = new_status
        borrow_req.save()

        # Update status barang sesuai kondisi
        if new_status == BorrowRequest.Status.APPROVED or new_status == BorrowRequest.Status.ONGOING:
            borrow_req.item.status = BorrowItem.Status.BORROWED
            borrow_req.item.save()
        elif new_status == BorrowRequest.Status.RETURNED:
            borrow_req.item.status = BorrowItem.Status.AVAILABLE
            borrow_req.item.save()

        messages.success(request, f'Status pengajuan diperbarui menjadi "{borrow_req.get_status_display()}".')
    else:
        messages.error(request, 'Status tidak valid.')

    return redirect('saling_pinjam:my_borrows')


from django import forms
from .models import Makanan


class MakananForm(forms.ModelForm):
    class Meta:
        model = Makanan
        fields = [
            'nama_makanan',
            'deskripsi',
            'porsi',
            'foto',
            'lokasi_pengambilan',
            'batas_layak_konsumsi',
        ]

        widgets = {
            'batas_layak_konsumsi': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}
            ),
            'deskripsi': forms.Textarea(
                attrs={'rows': 3}
            ),
        }

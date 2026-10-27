from django import forms
from .models import Makanan

class MakananForm(forms.ModelForm):
    class Meta:
        model = Makanan
        # Field yang boleh diisi oleh user
        fields = ['nama_makanan', 'deskripsi', 'porsi', 'foto', 'lokasi_pengambilan', 'batas_layak_konsumsi']
        
        # Widget ini bikin input 'batas_layak_konsumsi' otomatis jadi kalender keren di browser
        widgets = {
            'batas_layak_konsumsi': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'deskripsi': forms.Textarea(attrs={'rows': 3}),
        }
from django import forms

from .models import Grupo


class GrupoForm(forms.ModelForm):
    class Meta:
        model = Grupo
        fields = ['nombre']


class UnirseForm(forms.Form):
    codigo = forms.CharField(max_length=6)

    def clean_codigo(self):
        codigo = self.cleaned_data['codigo'].strip().upper()
        try:
            self.grupo = Grupo.objects.get(codigo=codigo)
        except Grupo.DoesNotExist:
            raise forms.ValidationError('No existe ningún grupo con ese código.')
        return codigo
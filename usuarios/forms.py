from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import Usuario


class RegistroForm(UserCreationForm):
    acepto_terminos = forms.BooleanField(
        required=True,
        error_messages={'required': 'Tienes que aceptar los términos de uso.'},
    )

    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ('username', 'email')

class RiotForm(forms.Form):
    REGIONES = [
        ('la1', 'LAN - Latinoamérica Norte'),
        ('la2', 'LAS - Latinoamérica Sur'),
        ('na1', 'NA - Norteamérica'),
        ('br1', 'BR - Brasil'),
        ('euw1', 'EUW - Europa Oeste'),
    ]

    riot_id = forms.CharField(max_length=40)
    region = forms.ChoiceField(choices=REGIONES)

    def clean_riot_id(self):
        riot_id = self.cleaned_data['riot_id'].strip()
        nombre, separador, tag = riot_id.partition('#')
        if not separador or not nombre or not tag:
            raise forms.ValidationError('Escribe tu Riot ID completo, con el #. Ejemplo: Faker#KR1')
        self.nombre = nombre.strip()
        self.tag = tag.strip()
        return riot_id
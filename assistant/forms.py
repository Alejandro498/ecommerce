from django import forms


USE_CASE_CHOICES = [
    ('gaming', 'Gaming / rendimiento'),
    ('trabajo', 'Trabajo / productividad'),
    ('estudio', 'Estudio / oficina'),
    ('streaming', 'Streaming / contenido'),
]


class AssistantForm(forms.Form):
    use_case = forms.ChoiceField(
        label='Necesidad principal',
        choices=USE_CASE_CHOICES,
        initial='gaming',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    budget = forms.IntegerField(
        label='Presupuesto (MXN)',
        min_value=2000,
        max_value=200000,
        initial=15000,
        widget=forms.NumberInput(attrs={'min': 2000, 'step': 500, 'class': 'form-control'}),
    )
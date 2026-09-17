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
    category = forms.ChoiceField(
        label='Categoría (opcional)',
        required=False,
        choices=[('', 'Cualquier categoría')],
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

    def __init__(self, *args, **kwargs):
        category_choices = kwargs.pop('category_choices', [])
        super().__init__(*args, **kwargs)
        if category_choices:
            self.fields['category'].choices = category_choices

        for field_name, defaults in {
            'use_case': 'gaming',
            'budget': 15000,
            'category': '',
        }.items():
            if not self.data.get(field_name) and field_name not in self.data:
                self.fields[field_name].initial = defaults

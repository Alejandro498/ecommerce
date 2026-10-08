from django import forms


USE_CASE_CHOICES = [
    ('gaming', 'Gaming / rendimiento'),
    ('trabajo', 'Trabajo / productividad'),
    ('estudio', 'Estudio / oficina'),
    ('streaming', 'Streaming / contenido'),
]

RESOLUTION_CHOICES = [
    ('office', 'Oficina / básico'),
    ('1080p', '1080p'),
    ('1440p', '1440p / 2K'),
    ('4k', '4K'),
]

PERFORMANCE_CHOICES = [
    ('bajo', 'Tranquilo / entrada'),
    ('medio', 'Equilibrado'),
    ('alto', 'Alto / exigente'),
]

EXPERIENCE_CHOICES = [
    ('principiante', 'Principiante'),
    ('medio', 'Intermedio'),
    ('avanzado', 'Avanzado'),
]

BRAND_CHOICES = [
    ('any', 'Me da igual'),
    ('amd', 'AMD'),
    ('intel', 'Intel'),
]

GPU_BRAND_CHOICES = [
    ('any', 'Me da igual'),
    ('nvidia', 'NVIDIA'),
    ('amd', 'AMD (Radeon)'),
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
    resolution = forms.ChoiceField(
        label='Resolución / uso de pantalla',
        choices=RESOLUTION_CHOICES,
        initial='1080p',
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    performance = forms.ChoiceField(
        label='Nivel de rendimiento',
        choices=PERFORMANCE_CHOICES,
        initial='medio',
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    experience = forms.ChoiceField(
        label='Tu experiencia',
        choices=EXPERIENCE_CHOICES,
        initial='medio',
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    brand = forms.ChoiceField(
        label='Marca de CPU',
        choices=BRAND_CHOICES,
        initial='any',
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    gpu_brand = forms.ChoiceField(
        label='Marca de GPU (opcional)',
        choices=GPU_BRAND_CHOICES,
        initial='any',
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

from django import forms
from .models import Order

class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['first_name', 'last_name', 'phone', 'email', 'addres_line_1', 'addres_line_2', 'country', 'state', 'city', 'order_note']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Optional checkout fields (blank detail / note should not block the order).
        self.fields['addres_line_2'].required = False
        self.fields['order_note'].required = False
        for name in (
            'first_name', 'last_name', 'phone', 'email',
            'addres_line_1', 'country', 'state', 'city',
        ):
            self.fields[name].required = True

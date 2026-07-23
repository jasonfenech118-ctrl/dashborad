from django.shortcuts import render


def dashboard(request):
    """Landing page for the Django rewrite. Links to the admin panel."""
    return render(request, "clinic/dashboard.html")

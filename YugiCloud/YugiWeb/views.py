from django.shortcuts import render

# Create your views here.
def accueil(request):
    return render(request, "page/index.html")
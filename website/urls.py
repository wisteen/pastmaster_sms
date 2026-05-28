from django.urls import path
from . import views

app_name = 'website'

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('admissions/', views.admissions, name='admissions'),
    path('gallery/', views.gallery, name='gallery'),
    path('newsletter/subscribe/', views.newsletter_subscribe, name='newsletter_subscribe'),
    path('admissions/inquiry/', views.admissions_inquiry, name='admissions_inquiry'),
    path('pages/<slug:slug>/', views.page_detail, name='page_detail'),
]

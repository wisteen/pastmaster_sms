from django.urls import path
from . import views_library

urlpatterns = [
    # Library Dashboard
    path('library/', views_library.library_dashboard, name='library_dashboard'),
    
    # Book Catalog
    path('library/catalog/', views_library.book_catalog, name='book_catalog'),
    path('library/books/add/', views_library.add_book, name='add_book'),
    path('library/books/issue/<int:book_id>/', views_library.issue_book, name='issue_book'),
    
    # Book Borrowing
    path('library/borrow/<int:book_id>/', views_library.borrow_book, name='borrow_book'),
    path('library/return/<int:borrowing_id>/', views_library.return_book, name='return_book'),
    path('library/my-borrowings/', views_library.my_borrowings, name='my_borrowings'),
    path('library/manage-borrowings/', views_library.manage_borrowings, name='manage_borrowings'),
    
    # Digital Resources
    path('library/digital/', views_library.digital_resources, name='digital_resources'),
    path('library/digital/add/', views_library.add_digital_resource, name='add_digital_resource'),
    path('library/digital/download/<int:resource_id>/', views_library.download_resource, name='download_resource'),
]
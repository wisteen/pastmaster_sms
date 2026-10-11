from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import (
    InventoryCategory,
    InventoryItem,
    InventoryStockMovement,
    InventorySupplier,
    SchoolMembership,
    SchoolTenant,
)
from .models_features import SchoolDomain
from .models_license import SystemLicense


User = get_user_model()


class FinancialInventoryTests(TestCase):
    host = 'inventory.testserver'

    def setUp(self):
        self.school = SchoolTenant.objects.create(name='Inventory School', slug='inventory-school')
        SchoolDomain.objects.create(school=self.school, domain=self.host)
        SystemLicense.all_objects.create(
            school=self.school,
            school_name=self.school.name,
            license_key='inventory-school-license',
            expiry_date=date.today() + timedelta(days=30),
        )
        self.admin = User.objects.create_user(username='admin', password='password', role='super_admin')
        SchoolMembership.objects.create(school=self.school, user=self.admin, primary_role='super_admin')
        self.client = Client(HTTP_HOST=self.host)
        self.assertTrue(self.client.login(username='admin', password='password'))

    def test_financial_dashboard_links_to_inventory(self):
        response = self.client.get(reverse('financial:financial_dashboard'))

        self.assertContains(response, reverse('financial:inventory_management'))
        self.assertContains(response, 'Inventory')

    def test_admin_can_create_inventory_item(self):
        category = InventoryCategory.all_objects.create(school=self.school, name='Stationery')
        supplier = InventorySupplier.all_objects.create(school=self.school, name='Office Supplier')

        response = self.client.post(reverse('financial:inventory_management'), {
            'action': 'save_item',
            'item-sku': 'PEN-001',
            'item-name': 'Blue Pen',
            'item-category': category.id,
            'item-supplier': supplier.id,
            'item-description': '',
            'item-unit': 'unit',
            'item-quantity_on_hand': '25',
            'item-reorder_level': '10',
            'item-unit_cost': '150.00',
            'item-location': 'Store',
            'item-status': 'active',
        })

        self.assertRedirects(response, reverse('financial:inventory_management'))
        item = InventoryItem.all_objects.get(school=self.school, sku='PEN-001')
        self.assertEqual(item.name, 'Blue Pen')
        self.assertEqual(item.quantity_on_hand, Decimal('25.00'))

    def test_stock_movements_update_quantity(self):
        category = InventoryCategory.all_objects.create(school=self.school, name='Supplies')
        item = InventoryItem.all_objects.create(
            school=self.school,
            category=category,
            sku='PAPER-001',
            name='A4 Paper',
            quantity_on_hand=Decimal('10.00'),
            reorder_level=Decimal('5.00'),
            unit_cost=Decimal('3000.00'),
        )

        response = self.client.post(reverse('financial:inventory_management'), {
            'action': 'save_movement',
            'movement-item': item.id,
            'movement-movement_type': 'in',
            'movement-quantity': '15',
            'movement-unit_cost': '3200.00',
            'movement-reference': 'INV-001',
            'movement-notes': '',
        })

        self.assertRedirects(response, reverse('financial:inventory_management'))
        item.refresh_from_db()
        self.assertEqual(item.quantity_on_hand, Decimal('25.00'))
        self.assertEqual(item.unit_cost, Decimal('3200.00'))
        self.assertEqual(InventoryStockMovement.all_objects.filter(item=item).count(), 1)

        response = self.client.post(reverse('financial:inventory_management'), {
            'action': 'save_movement',
            'movement-item': item.id,
            'movement-movement_type': 'out',
            'movement-quantity': '5',
            'movement-unit_cost': '',
            'movement-reference': 'REQ-001',
            'movement-notes': '',
        })

        self.assertRedirects(response, reverse('financial:inventory_management'))
        item.refresh_from_db()
        self.assertEqual(item.quantity_on_hand, Decimal('20.00'))

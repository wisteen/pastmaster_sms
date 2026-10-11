from datetime import date, timedelta
from unittest.mock import patch

from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from core.models import SchoolSettings, SchoolTenant
from core.models_features import SchoolDomain
from core.models_license import SystemLicense
from .models import WebsitePage
from .views import home


class HomeRedirectTests(TestCase):
    def setUp(self):
        self.school = SchoolTenant.objects.create(name='Redirect School', slug='redirect-school')
        SchoolDomain.objects.create(school=self.school, domain='redirect.testserver')
        SystemLicense.all_objects.create(
            school=self.school,
            school_name=self.school.name,
            license_key='redirect-school-license',
            expiry_date=date.today() + timedelta(days=30),
        )
        self.settings = SchoolSettings.all_objects.create(
            school=self.school,
            school_name=self.school.name,
            back_home_url='https://school.example.com/welcome?source=portal',
        )
        self.client = Client(HTTP_HOST='redirect.testserver')

    def test_default_home_redirects_before_loading_page(self):
        request = RequestFactory().get('/', HTTP_HOST='redirect.testserver')
        request.school = self.school
        with patch('website.views._resolve_page', side_effect=AssertionError('Homepage loaded before redirect')):
            response = home(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], self.settings.back_home_url)

    def test_cms_home_and_its_direct_url_redirect(self):
        page = WebsitePage.objects.create(
            school=self.school, title='Welcome', slug='welcome',
            is_homepage=True, is_published=True,
        )
        for url in (reverse('website:home'), reverse('website:page_detail', args=[page.slug])):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, self.settings.back_home_url, fetch_redirect_response=False)

    def test_legacy_home_slug_redirects(self):
        page, _ = WebsitePage.objects.update_or_create(
            school=self.school, slug='home',
            defaults={'title': 'Home', 'is_homepage': False, 'is_published': True},
        )
        response = self.client.get(reverse('website:page_detail', args=[page.slug]))
        self.assertRedirects(response, self.settings.back_home_url, fetch_redirect_response=False)

    def test_blank_setting_keeps_builtin_home(self):
        self.settings.back_home_url = ''
        self.settings.save(update_fields=['back_home_url'])
        response = self.client.get(reverse('website:home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'website/cms_page.html')

    def test_missing_settings_does_not_use_another_schools_url(self):
        other = SchoolTenant.objects.create(name='Other School', slug='other-school')
        SchoolDomain.objects.create(school=other, domain='other.testserver')
        response = Client(HTTP_HOST='other.testserver').get(reverse('website:home'))
        self.assertEqual(response.status_code, 200)

    def test_url_pointing_to_same_home_does_not_loop(self):
        self.settings.back_home_url = 'https://redirect.testserver/?source=portal#home'
        self.settings.save(update_fields=['back_home_url'])
        response = self.client.get(reverse('website:home'))
        self.assertEqual(response.status_code, 200)

    def test_other_pages_and_login_remain_accessible(self):
        page, _ = WebsitePage.objects.update_or_create(
            school=self.school, slug='about',
            defaults={'title': 'About', 'is_published': True},
        )
        for url in (page.get_absolute_url(), reverse('core:login')):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_clearing_url_takes_effect_immediately(self):
        self.assertEqual(self.client.get(reverse('website:home')).status_code, 302)
        self.settings.back_home_url = ''
        self.settings.save(update_fields=['back_home_url'])
        self.assertEqual(self.client.get(reverse('website:home')).status_code, 200)

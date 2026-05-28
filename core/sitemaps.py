from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from website.models import GalleryImage, WebsitePage


class StaticViewSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 1.0
    protocol = 'https'

    def items(self):
        pages = list(WebsitePage.objects.filter(is_published=True).order_by('school__name', 'order', 'title'))
        return pages or ['website:home']

    def location(self, item):
        if isinstance(item, str):
            return reverse(item)
        return item.get_absolute_url()

    def lastmod(self, item):
        return getattr(item, 'updated_at', None)


class NewsPostSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.8
    protocol = 'https'

    def items(self):
        return []


class GallerySitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.6
    protocol = 'https'

    def items(self):
        return WebsitePage.objects.filter(is_published=True, template_type='gallery').order_by('school__name', 'order', 'title')

    def location(self, item):
        return item.get_absolute_url()

    def lastmod(self, item):
        return item.updated_at


class ImageSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.7
    protocol = 'https'

    def items(self):
        images = []
        gallery_page = WebsitePage.objects.filter(is_published=True, template_type='gallery').first()
        gallery_location = gallery_page.get_absolute_url() if gallery_page else reverse('website:home')
        for image in GalleryImage.objects.select_related('school').all()[:100]:
            if image.image:
                images.append({
                    'loc': gallery_location,
                    'image': image.image.url,
                    'title': image.caption or 'School gallery',
                })
        return images

    def location(self, item):
        return item['loc']

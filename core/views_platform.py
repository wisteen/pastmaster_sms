from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms_platform import GlobalAdvertisementForm
from .models import GlobalAdvertisement


def _require_platform_superuser(request):
    if not request.user.is_superuser:
        raise PermissionDenied('Only the platform super administrator can manage global advertisements.')


@login_required
def global_advertisements(request):
    _require_platform_superuser(request)
    form = GlobalAdvertisementForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        advertisement = form.save(commit=False)
        advertisement.created_by = request.user
        advertisement.save()
        messages.success(request, 'The advertisement is now available across tenant portals according to its schedule.')
        return redirect('core:global_advertisements')

    advertisements = GlobalAdvertisement.objects.select_related('created_by').all()
    return render(request, 'platform/global_advertisements.html', {
        'form': form,
        'advertisements': advertisements,
        'editing_advertisement': None,
    })


@login_required
def global_advertisement_edit(request, advertisement_id):
    _require_platform_superuser(request)
    advertisement = get_object_or_404(GlobalAdvertisement, pk=advertisement_id)
    form = GlobalAdvertisementForm(
        request.POST or None,
        request.FILES or None,
        instance=advertisement,
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Advertisement updated.')
        return redirect('core:global_advertisements')
    advertisements = GlobalAdvertisement.objects.select_related('created_by').all()
    return render(request, 'platform/global_advertisements.html', {
        'form': form,
        'advertisements': advertisements,
        'editing_advertisement': advertisement,
    })


@login_required
@require_POST
def global_advertisement_toggle(request, advertisement_id):
    _require_platform_superuser(request)
    with transaction.atomic():
        advertisement = get_object_or_404(
            GlobalAdvertisement.objects.select_for_update(),
            pk=advertisement_id,
        )
        advertisement.is_active = not advertisement.is_active
        advertisement.save(update_fields=['is_active', 'updated_at'])
    messages.success(request, f"Advertisement {'activated' if advertisement.is_active else 'paused'}.")
    return redirect('core:global_advertisements')


@login_required
@require_POST
def global_advertisement_delete(request, advertisement_id):
    _require_platform_superuser(request)
    advertisement = get_object_or_404(GlobalAdvertisement, pk=advertisement_id)
    title = advertisement.title
    advertisement.delete()
    messages.success(request, f'Advertisement “{title}” was deleted.')
    return redirect('core:global_advertisements')

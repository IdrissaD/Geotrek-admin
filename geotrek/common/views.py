import mimetypes
import re
from django.apps import apps

from geotrek.feedback.parsers import SuricateParser
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import translation
from django.http import JsonResponse, Http404, HttpResponse, HttpResponseNotFound, HttpResponseRedirect
from django_celery_results.models import TaskResult
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.encoding import force_text
from django.views import static
from django.utils.translation import gettext as _
from django.views.generic import TemplateView
from django.views.generic import RedirectView, View
from django.views.decorators.http import require_POST, require_http_methods
from mapentity.helpers import api_bbox
from mapentity.registry import registry, app_settings
from mapentity import views as mapentity_views

from paperclip.views import _handle_attachment_form
from paperclip import settings as settings_paperclip

from geotrek.celery import app as celery_app
from geotrek.common.forms import AttachmentAccessibilityForm
from geotrek.common.mixins import transform_pdf_booklet_callback
from geotrek.common.utils import sql_extent
from geotrek.common.models import FileType, Attachment, TargetPortal, AccessibilityAttachment
from geotrek import __version__

from rest_framework import permissions as rest_permissions, viewsets

# async data imports
import ast
import os
import json
import redis
from urllib.parse import urljoin
from zipfile import ZipFile

from datetime import timedelta

from .permissions import PublicOrReadPermMixin
from .utils.import_celery import create_tmp_destination, discover_available_parsers

from .tasks import import_datas, import_datas_from_web
from .forms import ImportDatasetForm, ImportSuricateForm, ImportDatasetFormWithFile, SyncRandoForm
from .models import Theme
from .serializers import ThemeSerializer
from .tasks import launch_sync_rando


class MetaMixin:
    def get_context_data(self, **kwargs):
        lang = self.request.GET.get('lang')
        portal = self.request.GET.get('portal')
        context = super().get_context_data(**kwargs)
        context['FACEBOOK_APP_ID'] = settings.FACEBOOK_APP_ID
        context['FACEBOOK_IMAGE'] = urljoin(self.request.GET['rando_url'], settings.FACEBOOK_IMAGE)
        context['FACEBOOK_IMAGE_WIDTH'] = settings.FACEBOOK_IMAGE_WIDTH
        context['FACEBOOK_IMAGE_HEIGHT'] = settings.FACEBOOK_IMAGE_HEIGHT
        translation.activate(lang)
        context['META_TITLE'] = _('Geotrek Rando')
        translation.deactivate()
        if portal:
            try:
                target_portal = TargetPortal.objects.get(name=portal)
                context['FACEBOOK_APP_ID'] = target_portal.facebook_id
                context['FACEBOOK_IMAGE'] = urljoin(self.request.GET['rando_url'], target_portal.facebook_image_url)
                context['FACEBOOK_IMAGE_WIDTH'] = target_portal.facebook_image_width
                context['FACEBOOK_IMAGE_HEIGHT'] = target_portal.facebook_image_height
                context['META_TITLE'] = getattr(target_portal, 'title_{}'.format(lang))
            except TargetPortal.DoesNotExist:
                pass
        return context


class Meta(MetaMixin, TemplateView):
    template_name = 'common/meta.html'

    def get_context_data(self, **kwargs):
        lang = self.request.GET.get('lang')
        portal = self.request.GET.get('portal')
        context = super().get_context_data(**kwargs)
        translation.activate(lang)
        context['META_DESCRIPTION'] = _('Geotrek is a web app allowing you to prepare your next trekking trip !')
        translation.deactivate()
        if portal:
            try:
                target_portal = TargetPortal.objects.get(name=portal)
                context['META_DESCRIPTION'] = getattr(target_portal, 'description_{}'.format(lang))
            except TargetPortal.DoesNotExist:
                pass

        if 'geotrek.trekking' in settings.INSTALLED_APPS:
            from geotrek.trekking.models import Trek
            context['treks'] = Trek.objects.existing().order_by('pk').filter(
                Q(**{'published_{lang}'.format(lang=lang): True})
                | Q(**{'trek_parents__parent__published_{lang}'.format(lang=lang): True,
                       'trek_parents__parent__deleted': False})
            )
        if 'geotrek.tourism' in settings.INSTALLED_APPS:
            from geotrek.tourism.models import TouristicContent, TouristicEvent
            context['contents'] = TouristicContent.objects.existing().order_by('pk').filter(
                **{'published_{lang}'.format(lang=lang): True}
            )
            context['events'] = TouristicEvent.objects.existing().order_by('pk').filter(
                **{'published_{lang}'.format(lang=lang): True}
            )
        if 'geotrek.diving' in settings.INSTALLED_APPS:
            from geotrek.diving.models import Dive
            context['dives'] = Dive.objects.existing().order_by('pk').filter(
                **{'published_{lang}'.format(lang=lang): True}
            )
        return context


class FormsetMixin:
    context_name = None
    formset_class = None

    def form_valid(self, form):
        context = self.get_context_data()
        formset_form = context[self.context_name]

        if formset_form.is_valid():
            response = super().form_valid(form)
            formset_form.instance = self.object
            formset_form.save()
        else:
            response = self.form_invalid(form)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            try:
                context[self.context_name] = self.formset_class(
                    self.request.POST, instance=self.object)
            except ValidationError:
                pass
        else:
            context[self.context_name] = self.formset_class(
                instance=self.object)
        return context


class DocumentPublicMixin:
    template_name_suffix = "_public"

    # Override view_permission_required
    def dispatch(self, *args, **kwargs):
        return super(mapentity_views.MapEntityDocumentBase, self).dispatch(*args, **kwargs)

    def get(self, request, pk, slug, lang=None):
        obj = get_object_or_404(self.model, pk=pk)
        try:
            file_type = FileType.objects.get(type="Topoguide")
        except FileType.DoesNotExist:
            file_type = None
        attachments = Attachment.objects.attachments_for_object_only_type(obj, file_type)
        if not attachments and not settings.ONLY_EXTERNAL_PUBLIC_PDF:
            return super().get(request, pk, slug, lang)
        if not attachments:
            return HttpResponseNotFound("No attached file with 'Topoguide' type.")
        path = attachments[0].attachment_file.name

        if settings.DEBUG:
            response = static.serve(self.request, path, settings.MEDIA_ROOT)
        else:
            response = HttpResponse()
            response[settings.MAPENTITY_CONFIG['SENDFILE_HTTP_HEADER']] = os.path.join(settings.MEDIA_URL_SECURE, path)
        response["Content-Type"] = 'application/pdf'
        response['Content-Disposition'] = "attachment; filename={0}.pdf".format(slug)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        modelname = self.get_model()._meta.object_name.lower()
        context['mapimage_ratio'] = settings.EXPORT_MAP_IMAGE_SIZE[modelname]
        return context


class BookletMixin:

    def get(self, request, pk, slug, lang=None):
        response = super().get(request, pk, slug)
        response.add_post_render_callback(transform_pdf_booklet_callback)
        return response


class DocumentPublic(PublicOrReadPermMixin, DocumentPublicMixin, mapentity_views.MapEntityDocumentWeasyprint):
    pass


class DocumentBookletPublic(PublicOrReadPermMixin, DocumentPublicMixin, BookletMixin,
                            mapentity_views.MapEntityDocumentWeasyprint):
    pass


class MarkupPublic(PublicOrReadPermMixin, DocumentPublicMixin, mapentity_views.MapEntityMarkupWeasyprint):
    pass


class CompletenessMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        modelname = self.get_model()._meta.object_name.lower()
        if modelname in settings.COMPLETENESS_FIELDS:
            context['completeness_fields'] = settings.COMPLETENESS_FIELDS[modelname]
        return context


#
# Concrete views
# ..............................


class JSSettings(mapentity_views.JSSettings):

    """ Override mapentity base settings in order to provide
    Geotrek necessary stuff.
    """
    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_context_data(self):
        dictsettings = super().get_context_data()
        # Add extra stuff (edition, labelling)
        dictsettings['map'].update(
            snap_distance=settings.SNAP_DISTANCE,
            paths_line_marker=settings.PATHS_LINE_MARKER,
            colorspool=settings.COLORS_POOL,
        )
        dictsettings['version'] = __version__
        dictsettings['showExtremities'] = settings.SHOW_EXTREMITIES
        dictsettings['showLabels'] = settings.SHOW_LABELS
        return dictsettings


@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_check_extents(request):
    """
    This view allows administrators to visualize data and configured extents.

    Since it's the first, we implemented this in a very rough way. If there is
    to be more admin tools like this one. Move this to a separate Django app and
    style HTML properly.
    """
    path_extent_native = sql_extent("SELECT ST_Extent(geom) FROM core_path;")
    path_extent = api_bbox(path_extent_native)
    dem_extent_native = sql_extent(
        "SELECT ST_Extent(rast::geometry) FROM altimetry_dem;")
    dem_extent = api_bbox(dem_extent_native)
    tiles_extent_native = settings.SPATIAL_EXTENT
    tiles_extent = api_bbox(tiles_extent_native)
    viewport_native = settings.LEAFLET_CONFIG['SPATIAL_EXTENT']
    viewport = api_bbox(viewport_native, srid=settings.API_SRID)

    def leafletbounds(bbox):
        return [[bbox[1], bbox[0]], [bbox[3], bbox[2]]]

    context = dict(
        path_extent=leafletbounds(path_extent),
        path_extent_native=path_extent_native,
        dem_extent=leafletbounds(dem_extent) if dem_extent else None,
        dem_extent_native=dem_extent_native,
        tiles_extent=leafletbounds(tiles_extent),
        tiles_extent_native=tiles_extent_native,
        viewport=leafletbounds(viewport),
        viewport_native=viewport_native,
        SRID=settings.SRID,
        API_SRID=settings.API_SRID,
    )
    return render(request, 'common/check_extents.html', context)


class UserArgMixin:

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


def import_file(uploaded, parser, encoding, user_pk):
    destination_dir, destination_file = create_tmp_destination(uploaded.name)
    with open(destination_file, 'wb+') as f:
        f.write(uploaded.file.read())
        zfile = ZipFile(f)
        for name in zfile.namelist():
            zfile.extract(name, os.path.dirname(os.path.realpath(f.name)))
            if name.endswith('shp'):
                import_datas.delay(name=parser.__name__, filename='/'.join((destination_dir, name)),
                                   module=parser.__module__, encoding=encoding, user=user_pk)


@login_required
def import_view(request):
    """
    Gets the existing declared parsers for the current project.
    This view handles only the file based import parsers.
    """
    choices = []
    choices_url = []
    render_dict = {}

    choices, choices_url, classes = discover_available_parsers(request.user)
    choices_suricate = [("everything", _("Reports"))]

    form = ImportDatasetFormWithFile(choices, prefix="with-file")
    form_without_file = ImportDatasetForm(
        choices_url, prefix="without-file")
    form_suricate = ImportSuricateForm(choices_suricate)

    if request.method == 'POST':
        if 'upload-file' in request.POST:
            form = ImportDatasetFormWithFile(
                choices, request.POST, request.FILES, prefix="with-file")

            if form.is_valid():
                uploaded = request.FILES['with-file-zipfile']
                parser = classes[int(form['parser'].value())]
                encoding = form.cleaned_data['encoding']
                try:
                    import_file(uploaded, parser, encoding, request.user.pk)
                except UnicodeDecodeError:
                    render_dict['encoding_error'] = True

        if 'import-web' in request.POST:
            form_without_file = ImportDatasetForm(
                choices_url, request.POST, prefix="without-file")

            if form_without_file.is_valid():
                parser = classes[int(form_without_file['parser'].value())]
                import_datas_from_web.delay(
                    name=parser.__name__, module=parser.__module__, user=request.user.pk
                )

        if 'import-suricate' in request.POST:
            form_suricate = ImportSuricateForm(choices_suricate, request.POST)
            if form_suricate.is_valid() and settings.SURICATE_MANAGEMENT_ENABLED:
                parser = SuricateParser()
                parser.get_statuses()
                parser.get_activities()
                parser.get_alerts(verbosity=1)

    # Hide second form if parser has no web based imports.
    if choices:
        render_dict['form'] = form
    if choices_url:
        render_dict['form_without_file'] = form_without_file
    if settings.SURICATE_MANAGEMENT_ENABLED:
        render_dict['form_suricate'] = form_suricate

    return render(request, 'common/import_dataset.html', render_dict)


@login_required
def import_update_json(request):
    results = []
    threshold = timezone.now() - timedelta(seconds=60)
    for task in TaskResult.objects.filter(date_done__gte=threshold).order_by('date_done'):
        json_results = json.loads(task.result)
        if json_results.get('name', '').startswith('geotrek.common'):
            results.append(
                {
                    'id': task.task_id,
                    'result': json_results or {'current': 0, 'total': 0},
                    'status': task.status
                }
            )
    i = celery_app.control.inspect(['celery@geotrek'])
    try:
        reserved = i.reserved()
    except redis.exceptions.ConnectionError:
        reserved = None
    tasks = [] if reserved is None else reversed(reserved['celery@geotrek'])
    for task in tasks:
        if task['name'].startswith('geotrek.common'):
            args = ast.literal_eval(task['args'])
            if task['name'].endswith('import-file'):
                filename = os.path.basename(args[1])
            else:
                filename = _("Import from web.")
            results.append(
                {
                    'id': task['id'],
                    'result': {
                        'parser': args[0],
                        'filename': filename,
                        'current': 0,
                        'total': 0
                    },
                    'status': 'PENDING',
                }
            )

    return HttpResponse(json.dumps(results), content_type="application/json")


class ThemeViewSet(viewsets.ModelViewSet):
    model = Theme
    queryset = Theme.objects.all()
    permission_classes = [rest_permissions.DjangoModelPermissionsOrAnonReadOnly]
    serializer_class = ThemeSerializer

    def get_queryset(self):
        return super().get_queryset().order_by('id')


class ParametersView(View):
    def get(request, *args, **kwargs):
        response = {
            'geotrek_admin_version': settings.VERSION,
        }
        return JsonResponse(response)


@login_required
def last_list(request):
    last = request.session.get('last_list')  # set in MapEntityList
    for entity in registry.entities:
        if reverse(entity.url_list) == last and request.user.has_perm(entity.model.get_permission_codename('list')):
            return redirect(entity.url_list)
    for entity in registry.entities:
        if entity.menu and request.user.has_perm(entity.model.get_permission_codename('list')):
            return redirect(entity.url_list)
    return redirect('trekking:trek_list')


@login_required
@user_passes_test(lambda u: u.is_superuser)
def sync_view(request):
    """
    Custom views to view / track / launch a sync rando
    """

    return render(request,
                  'common/sync_rando.html',
                  {'form': SyncRandoForm(), },
                  )


@login_required
@user_passes_test(lambda u: u.is_superuser)
def sync_update_json(request):
    """
    get info from sync_rando celery_task
    """
    results = []
    threshold = timezone.now() - timedelta(seconds=60)
    for task in TaskResult.objects.filter(date_done__gte=threshold, status='PROGRESS'):
        json_results = json.loads(task.result)
        if json_results.get('name', '').startswith('geotrek.trekking'):
            results.append({
                'id': task.task_id,
                'result': json_results or {'current': 0,
                                           'total': 0},
                'status': task.status
            })
    i = celery_app.control.inspect(['celery@geotrek'])
    try:
        reserved = i.reserved()
    except redis.exceptions.ConnectionError:
        reserved = None
    tasks = [] if reserved is None else reversed(reserved['celery@geotrek'])
    for task in tasks:
        if task['name'].startswith('geotrek.trekking'):
            results.append(
                {
                    'id': task['id'],
                    'result': {'current': 0, 'total': 0},
                    'status': 'PENDING',
                }
            )
    for task in TaskResult.objects.filter(date_done__gte=threshold, status='FAILURE').order_by('-date_done'):
        json_results = json.loads(task.result)
        if json_results.get('name', '').startswith('geotrek.trekking'):
            results.append({
                'id': task.task_id,
                'result': json_results or {'current': 0,
                                           'total': 0},
                'status': task.status
            })

    return HttpResponse(json.dumps(results),
                        content_type="application/json")


class SyncRandoRedirect(RedirectView):
    http_method_names = ['post']
    pattern_name = 'common:sync_randos_view'

    @method_decorator(login_required)
    @method_decorator(user_passes_test(lambda u: u.is_superuser))
    def post(self, request, *args, **kwargs):
        url = "{scheme}://{host}".format(scheme='https' if self.request.is_secure() else 'http',
                                         host=self.request.get_host())
        self.job = launch_sync_rando.delay(url=url)
        return super().post(request, *args, **kwargs)


class ServeAttachmentAccessibility(View):

    def get(self, request, *args, **kwargs):
        """
            Serve media/ for authorized users only, since it can contain sensitive
            information (uploaded documents)
        """
        path = kwargs['path']
        original_path = re.sub(settings.MAPENTITY_CONFIG['REGEX_PATH_ATTACHMENTS'], '', path, count=1,
                               flags=re.IGNORECASE)
        if not AccessibilityAttachment.objects.filter(attachment_accessibility_file=original_path):
            raise Http404('No attachments for accessibility matches the given query.')

        attachments = AccessibilityAttachment.objects.filter(attachment_accessibility_file=original_path)
        obj = attachments.first().content_object
        if not hasattr(obj._meta.model, 'attachments_accessibility'):
            raise Http404
        if not obj.is_public():
            if not request.user.is_authenticated:
                raise PermissionDenied
            if not request.user.has_perm(settings_paperclip.get_attachment_permission('read_attachment')):
                raise PermissionDenied
            if not request.user.has_perm('{}.read_{}'.format(obj._meta.app_label, obj._meta.model_name)):
                raise PermissionDenied

        content_type, encoding = mimetypes.guess_type(path)

        if settings.DEBUG:
            response = static.serve(request, path, settings.MEDIA_ROOT)
        else:
            response = HttpResponse()
            response[settings.MAPENTITY_CONFIG['SENDFILE_HTTP_HEADER']] = os.path.join(settings.MEDIA_URL_SECURE, path)
        response["Content-Type"] = content_type or 'application/octet-stream'
        if app_settings['SERVE_MEDIA_AS_ATTACHMENT']:
            response['Content-Disposition'] = "attachment; filename={0}".format(
                os.path.basename(path))
        return response


@require_POST
@permission_required(settings_paperclip.get_attachment_permission('add_attachment'), raise_exception=True)
def add_attachment_accessibility(request, app_label, model_name, pk,
                                 attachment_form=AttachmentAccessibilityForm,
                                 extra_context=None):
    model = apps.get_model(app_label, model_name)
    obj = get_object_or_404(model, pk=pk)

    form = attachment_form(request, request.POST, request.FILES, object=obj)
    return _handle_attachment_form(request, obj, form,
                                   _('Add attachment %s'),
                                   _('Your attachment was uploaded.'),
                                   extra_context)


@require_http_methods(["GET", "POST"])
@permission_required(settings_paperclip.get_attachment_permission('change_attachment'), raise_exception=True)
def update_attachment_accessibility(request, attachment_pk,
                                    attachment_form=AttachmentAccessibilityForm,
                                    extra_context=None):
    attachment = get_object_or_404(AccessibilityAttachment, pk=attachment_pk)
    obj = attachment.content_object
    if request.method == 'POST':
        form = attachment_form(
            request, request.POST, request.FILES,
            instance=attachment,
            object=obj)
    else:
        form = attachment_form(
            request,
            instance=attachment,
            object=obj)
    return _handle_attachment_form(request, obj, form,
                                   _('Update attachment %s'),
                                   _('Your attachment was updated.'),
                                   extra_context)


@permission_required(settings_paperclip.get_attachment_permission('delete_attachment'), raise_exception=True)
def delete_attachment_accessibility(request, attachment_pk):
    g = get_object_or_404(AccessibilityAttachment, pk=attachment_pk)
    obj = g.content_object
    can_delete = (request.user.has_perm(
        settings_paperclip.get_attachment_permission('delete_attachment_others')) or request.user == g.creator)
    if can_delete:
        g.delete()
        if settings_paperclip.PAPERCLIP_ACTION_HISTORY_ENABLED:
            LogEntry.objects.log_action(
                user_id=request.user.pk,
                content_type_id=g.content_type.id,
                object_id=g.object_id,
                object_repr=force_text(obj),
                action_flag=CHANGE,
                change_message=_('Remove attachment %s') % g.title,
            )
        messages.success(request, _('Your attachment was deleted.'))
    else:
        error_msg = _('You are not allowed to delete this attachment.')
        messages.error(request, error_msg)
    return HttpResponseRedirect(f"{obj.get_detail_url()}?tab=attachments-accessibility")


home = last_list

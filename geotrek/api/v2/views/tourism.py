from django.conf import settings
from django.contrib.gis.db.models.functions import Transform
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils.translation import activate

from rest_framework.response import Response

from geotrek.api.v2 import serializers as api_serializers, \
    filters as api_filters, viewsets as api_viewsets
from geotrek.tourism import models as tourism_models


class LabelAccessibilityViewSet(api_viewsets.GeotrekViewSet):
    serializer_class = api_serializers.LabelAccessibilitySerializer
    queryset = tourism_models.LabelAccessibility.objects.order_by('pk')  # Required for reliable pagination


class TouristicContentCategoryViewSet(api_viewsets.GeotrekViewSet):
    filter_backends = api_viewsets.GeotrekViewSet.filter_backends + (api_filters.TouristicContentRelatedPortalFilter,)
    serializer_class = api_serializers.TouristicContentCategorySerializer
    queryset = tourism_models.TouristicContentCategory.objects \
        .prefetch_related('types') \
        .order_by('pk')  # Required for reliable pagination

    def retrieve(self, request, pk=None, format=None):
        # Allow to retrieve objects even if not visible in list view
        elem = get_object_or_404(tourism_models.TouristicContentCategory, pk=pk)
        serializer = api_serializers.TouristicContentCategorySerializer(elem, many=False, context={'request': request})
        return Response(serializer.data)


class TouristicContentViewSet(api_viewsets.GeotrekGeometricViewset):
    filter_backends = api_viewsets.GeotrekGeometricViewset.filter_backends + (
        api_filters.GeotrekTouristicContentFilter,
        api_filters.NearbyContentFilter,
        api_filters.UpdateOrCreateDateFilter
    )
    serializer_class = api_serializers.TouristicContentSerializer

    def get_queryset(self):
        activate(self.request.GET.get('language'))
        return tourism_models.TouristicContent.objects.existing()\
            .select_related('category', 'reservation_system', 'label_accessibility') \
            .prefetch_related('source', 'themes', 'type1', 'type2') \
            .annotate(geom_transformed=Transform(F('geom'), settings.API_SRID)) \
            .order_by('name')  # Required for reliable pagination


class InformationDeskTypeViewSet(api_viewsets.GeotrekViewSet):
    serializer_class = api_serializers.InformationDeskTypeSerializer
    queryset = tourism_models.InformationDeskType.objects.order_by('pk')


class InformationDeskViewSet(api_viewsets.GeotrekViewSet):
    filter_backends = api_viewsets.GeotrekViewSet.filter_backends + (api_filters.TrekRelatedPortalFilter,
                                                                     api_filters.NearbyContentFilter,
                                                                     api_filters.GeotrekInformationDeskFilter)
    serializer_class = api_serializers.InformationDeskSerializer

    def get_queryset(self):
        activate(self.request.GET.get('language'))
        return tourism_models.InformationDesk.objects.select_related('label_accessibility', 'type').order_by('name')

    def retrieve(self, request, pk=None, format=None):
        # Allow to retrieve objects even if not visible in list view
        elem = get_object_or_404(tourism_models.InformationDesk, pk=pk)
        serializer = api_serializers.InformationDeskSerializer(elem, many=False, context={'request': request})
        return Response(serializer.data)


class TouristicEventTypeViewSet(api_viewsets.GeotrekViewSet):
    filter_backends = api_viewsets.GeotrekViewSet.filter_backends + (api_filters.TouristicEventRelatedPortalFilter, )
    serializer_class = api_serializers.TouristicEventTypeSerializer
    queryset = tourism_models.TouristicEventType.objects.order_by('pk')  # Required for reliable pagination


class TouristicEventViewSet(api_viewsets.GeotrekGeometricViewset):
    filter_backends = api_viewsets.GeotrekGeometricViewset.filter_backends + (
        api_filters.GeotrekTouristicEventFilter,
        api_filters.NearbyContentFilter,
        api_filters.UpdateOrCreateDateFilter
    )
    serializer_class = api_serializers.TouristicEventSerializer

    def get_queryset(self):
        activate(self.request.GET.get('language'))
        return tourism_models.TouristicEvent.objects.existing()\
            .select_related('type') \
            .prefetch_related('themes', 'source', 'portal') \
            .annotate(geom_transformed=Transform(F('geom'), settings.API_SRID)) \
            .order_by('name')  # Required for reliable pagination
